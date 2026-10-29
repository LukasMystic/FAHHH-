#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <MFRC522.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <atomic>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

// SIC8 fictional A -> B/C journey prototype. Pins match C1/Wokwi.
// Station layout and train events are simulations. No train, door, or gap-width
// detection is claimed from the cane hardware. MQTT only reports to C3 topics.
// New journey event names/DEMO_* station IDs need a C3 contract update before PR.
// Local alerts never wait for Wi-Fi or MQTT.
// Distance correction assumes the HC-SR04 beam aligns with the cane/MPU axis.
// Calibrate the physical mounting angle before any real-world use.
const int TRIG=26, ECHO=27, SDA_MPU=21, SCL_MPU=22;
const int RFID_SS=5, RFID_RST=4, ENC_CLK=32, ENC_DT=33, ENC_SW=25;
const int SOS=13, BUZZ=14, LED_GETAR=17, BEACON=34;
MFRC522 rfid(RFID_SS, RFID_RST);

enum State { SELECT_DEST, SEEK_PLATFORM, WAIT_TRAIN, ON_TRAIN, ARRIVING, COMPLETE, EMERGENCY };
enum RouteStyle { FLAT_ROUTE, LIFT_ROUTE, RAMP_ROUTE };
enum PlatformSide { P1, P2 };
enum JourneyPhase { TO_ORIGIN_PLATFORM, AT_ORIGIN_PLATFORM, ONBOARD, VERIFY_DEST_PLATFORM, TO_DEST_EXIT, DONE };
State state=SELECT_DEST;
JourneyPhase phase=TO_ORIGIN_PLATFORM;
RouteStyle originRoute=FLAT_ROUTE, destRoute=FLAT_ROUTE;
PlatformSide originSide=P1, destSide=P1, trainSide=P1;
char destLetter='B';
unsigned originProgress=0, destProgress=0;
char lastCheckpoint[28]="";
char lastStation[12]="";
bool destinationConfirmed=false;
bool trainIdentityValid=false, trainStopped=false, doorOpen=false, boardingReady=false;
bool destinationArrived=false;
bool trainNear=false, edge=false, edgeNeedsCorrectedClear=false, tiltAlert=false, help=false;
bool distanceRawFallback=false, ultrasonicFault=false, mpuFault=false;
float rawDistanceCm=NAN, distanceCm=NAN, baseline=NAN, rawBaseline=NAN, tiltDeg=NAN;
float beaconRssiDbm=NAN;
int beaconAdc=0, edgeHits=0;
unsigned long lastDistance=0,lastMpu=0,lastBeacon=0,lastStatus=0,edgeSafeSince=0,tiltSince=0;
unsigned long lastMqttStatus=0;
uint32_t loopMaxUs=0;
String serialLine;

constexpr char WIFI_SSID[]="Wokwi-GUEST";
constexpr char WIFI_PASSWORD[]="";
constexpr char MQTT_HOST[]="broker.hivemq.com";
constexpr uint16_t MQTT_PORT=8883;
constexpr char MQTT_CLIENT_ID[]="fahhh-esp32-unit-01";
constexpr char MQTT_EVENTS_TOPIC[]="sic8/fahhh/device/events";
constexpr char MQTT_STATUS_TOPIC[]="sic8/fahhh/device/status";
constexpr char MQTT_ONLINE_TOPIC[]="sic8/fahhh/device/online";

enum class MqttTxKind : uint8_t { Event, Status };
struct MqttTxMessage { MqttTxKind kind; char json[200]; };
QueueHandle_t mqttQueue=nullptr;
std::atomic<bool> mqttReady{false};
std::atomic<uint32_t> mqttDropped{0};

float jsonNumber(float value){return isfinite(value)?value:-1.0f;}

// Called by the sensor loop only. No network operation or wait occurs here.
bool queueMqttJson(MqttTxKind kind,const char *json){
  if(!mqttQueue || !mqttReady.load()){mqttDropped.fetch_add(1);return false;}
  MqttTxMessage message{};
  message.kind=kind;
  int n=snprintf(message.json,sizeof(message.json),"%s",json);
  if(n<0 || n>=(int)sizeof(message.json)){mqttDropped.fetch_add(1);return false;}
  if(xQueueSend(mqttQueue,&message,0)!=pdTRUE){mqttDropped.fetch_add(1);return false;}
  return true;
}

constexpr unsigned long SOS_HOLD_MS=3000;
constexpr unsigned long SOS_DEBOUNCE_MS=40;
constexpr float MAX_EDGE_TILT_DEG=65.0f;
// Equivalent to the prior demo ADC thresholds: enter >2600, leave <=2100.
constexpr float BEACON_NEAR_DBM=-100.0f+2600.0f*60.0f/4095.0f;
constexpr float BEACON_FAR_DBM=-100.0f+2100.0f*60.0f/4095.0f;

// In Wokwi, potentiometer values 0..4095 represent RSSI -100..-40 dBm.
// On physical hardware, replace this function body with a BLE scan result.
float readDoorBeaconRSSI() {
  beaconAdc=analogRead(BEACON);
  return -100.0f+beaconAdc*60.0f/4095.0f;
}

// Project the slant range onto vertical height. NaN selects the raw ultrasonic
// fallback when the MPU reading is missing or the cane is tilted too far.
float correctedGroundDistanceCm(float measuredCm,float caneTiltDeg) {
  if(!isfinite(measuredCm) || !isfinite(caneTiltDeg) || caneTiltDeg>MAX_EDGE_TILT_DEG)return NAN;
  return measuredCm*cosf(caneTiltDeg*PI/180.0f);
}

const char *stateName(State s) {
  switch(s) {
    case SELECT_DEST:return "SELECT_DEST";
    case SEEK_PLATFORM:return "SEEK_PLATFORM"; case WAIT_TRAIN:return "WAIT_TRAIN";
    case ON_TRAIN:return "ON_TRAIN"; case ARRIVING:return "ARRIVING";
    case COMPLETE:return "COMPLETE"; default:return "EMERGENCY";
  }
}
const char *routeName(RouteStyle r) {
  return r==LIFT_ROUTE?"LIFT":r==RAMP_ROUTE?"RAMP":"FLAT";
}
const char *sideName(PlatformSide s) { return s==P1?"P1":"P2"; }
const char *phaseName(JourneyPhase p) {
  switch(p) {
    case TO_ORIGIN_PLATFORM:return "TO_ORIGIN_PLATFORM";
    case AT_ORIGIN_PLATFORM:return "AT_ORIGIN_PLATFORM";
    case ONBOARD:return "ONBOARD";
    case VERIFY_DEST_PLATFORM:return "VERIFY_DEST_PLATFORM";
    case TO_DEST_EXIT:return "TO_DEST_EXIT";
    default:return "DONE";
  }
}
const char *destStationId() { return destLetter=='B'?"DEMO_B":"DEMO_C"; }
String originNodeAt(unsigned index) {
  if(index==0)return "A_MASUK";
  if(originRoute==FLAT_ROUTE){
    if(index==1)return "A_SIMPANG";
  } else if(originRoute==LIFT_ROUTE){
    if(index==1)return "A_LIFT_LOBI";
    if(index==2)return "A_LIFT_PERON";
  } else {
    if(index==1)return "A_RAMP_AWAL";
    if(index==2)return "A_RAMP_AKHIR";
  }
  return String("A_")+sideName(originSide)+"_WAIT";
}
unsigned originNodeCount() { return originRoute==FLAT_ROUTE?3:4; }
String destNodeAt(unsigned index) {
  String prefix=String(destLetter)+"_";
  if(index==0)return prefix+sideName(destSide)+"_PERON";
  if(destRoute==FLAT_ROUTE){
    if(index==1)return prefix+"SIMPANG";
  } else if(destRoute==LIFT_ROUTE){
    if(index==1)return prefix+"LIFT_PERON";
    if(index==2)return prefix+"LIFT_LOBI";
  } else {
    if(index==1)return prefix+"RAMP_AWAL";
    if(index==2)return prefix+"RAMP_AKHIR";
  }
  return prefix+"LUAR";
}
unsigned destNodeCount() { return destRoute==FLAT_ROUTE?3:4; }
void queueMqttEvent(const char *name,const char *source){
  char json[200];
  int n=snprintf(json,sizeof(json),
    "{\"device_id\":\"unit-01\",\"uptime_s\":%lu,\"event\":\"%s\",\"state\":\"%s\",\"source\":\"%s\",\"distance_cm\":%.0f}",
    millis()/1000UL,name,stateName(state),source,jsonNumber(distanceCm));
  if(n<0 || n>=(int)sizeof(json)){mqttDropped.fetch_add(1);return;}
  queueMqttJson(MqttTxKind::Event,json);
}
void queueMqttStatus(){
  if(millis()-lastMqttStatus<2000UL)return;
  lastMqttStatus=millis();
  const char *station=lastStation;
  const char *dest=destinationConfirmed?destStationId():"";
  char json[200];
  int n=snprintf(json,sizeof(json),
    "{\"device_id\":\"unit-01\",\"uptime_s\":%lu,\"state\":\"%s\",\"distance_cm\":%.0f,\"tilt_deg\":%.0f,"
    "\"edge\":%d,\"train_near\":%d,\"help\":%d,\"station\":\"%s\",\"dest\":\"%s\"}",
    millis()/1000UL,stateName(state),jsonNumber(distanceCm),jsonNumber(tiltDeg),
    edge?1:0,trainNear?1:0,help?1:0,station,dest);
  if(n<0 || n>=(int)sizeof(json)){mqttDropped.fetch_add(1);return;}
  queueMqttJson(MqttTxKind::Status,json);
}
void event(const char *name,const char *source) {
  Serial.printf("EVENT t=%lu event=%s state=%s source=%s distance_cm=%.1f beacon_adc=%d\n",millis(),name,stateName(state),source,distanceCm,beaconAdc);
  queueMqttEvent(name,source);
}
void changeState(State next,const char *source) {
  if(state==next)return;
  Serial.printf("STATE %s -> %s source=%s\n",stateName(state),stateName(next),source);
  state=next; event(stateName(next),source);
}

// Edge cues take priority over fault cues; both can interrupt the help alarm.
enum AlertKind { NAV_ALERT, EDGE_ALERT, FAULT_ALERT, HELP_ALERT };
struct Pattern { int count,onMs,offMs,hz,step; unsigned long next; AlertKind kind; } pat={0,0,0,0,0,0,NAV_ALERT};
bool pendingEdgePulse=false, pendingFaultPulse=false, resumeHelpPulse=false;
void pulse(int count,int onMs,int offMs,int hz,AlertKind kind=NAV_ALERT) {
  if(kind==NAV_ALERT && (help || edge || (pat.count && pat.kind!=NAV_ALERT)))return;
  if(kind==HELP_ALERT){
    if(edge || (pat.count && pat.kind==EDGE_ALERT))pendingEdgePulse=true;
    if(ultrasonicFault || mpuFault || (pat.count && pat.kind==FAULT_ALERT))pendingFaultPulse=true;
    resumeHelpPulse=false;
  }
  if(kind==FAULT_ALERT && (pendingEdgePulse || (pat.count && pat.kind==EDGE_ALERT))){
    pendingFaultPulse=true;
    if(help)resumeHelpPulse=true;
    return; // Never delay an active or queued edge warning with a fault pattern.
  }
  if(kind==EDGE_ALERT && pat.count && pat.kind==FAULT_ALERT)pendingFaultPulse=true;
  if((kind==EDGE_ALERT || kind==FAULT_ALERT) && help)resumeHelpPulse=true;
  pat={count,onMs,offMs,hz,0,millis(),kind};
}
void servicePulse() {
  if(pendingEdgePulse && (!pat.count || pat.kind==HELP_ALERT)){
    pendingEdgePulse=false;pulse(1,700,100,1200,EDGE_ALERT);
  } else if(pendingFaultPulse && (!pat.count || pat.kind==HELP_ALERT)){
    pendingFaultPulse=false;pulse(2,500,180,500,FAULT_ALERT);
  }
  if(!pat.count && resumeHelpPulse && help){resumeHelpPulse=false;pat={4,250,140,1600,0,millis(),HELP_ALERT};}
  if(!pat.count || millis()<pat.next)return;
  bool on=(pat.step%2)==0;
  digitalWrite(LED_GETAR,on?HIGH:LOW);
  if(on)tone(BUZZ,pat.hz); else noTone(BUZZ);
  pat.next=millis()+(on?pat.onMs:pat.offMs);
  pat.step++;
  if(pat.step>=pat.count*2)pat.count=0;
}

volatile int encoderSteps=0;
void IRAM_ATTR encoderTick() { encoderSteps+=digitalRead(ENC_DT)==HIGH?1:-1; }
void menuMove(int dir) {
  if(state!=SELECT_DEST || help)return;
  destLetter=destLetter=='B'?'C':'B';
  Serial.printf("MENU destination=%s (fictional); press encoder to confirm\n",destStationId());
  pulse(1,45,50,650);
}
void resetJourney(const char *source) {
  pat.count=0;pendingEdgePulse=false;pendingFaultPulse=false;resumeHelpPulse=false;
  noTone(BUZZ);digitalWrite(LED_GETAR,LOW);
  destinationConfirmed=false;originProgress=0;destProgress=0;
  lastCheckpoint[0]=0;lastStation[0]=0;
  trainIdentityValid=false;trainStopped=false;doorOpen=false;boardingReady=false;
  destinationArrived=false;trainNear=false;
  phase=TO_ORIGIN_PLATFORM;
  changeState(SELECT_DEST,source);
  Serial.printf("MENU destination=%s; config origin=%s dest=%s sides=%s/%s\n",
    destStationId(),routeName(originRoute),routeName(destRoute),sideName(originSide),sideName(destSide));
}
void encoderPress() {
  if(state!=SELECT_DEST || help)return;
  destinationConfirmed=true;originProgress=0;destProgress=0;
  phase=TO_ORIGIN_PLATFORM;
  changeState(SEEK_PLATFORM,"encoder_button");
  Serial.printf("ROUTE destination=%s origin=%s dest_exit=%s origin_side=%s dest_side=%s next=%s\n",
    destStationId(),routeName(originRoute),routeName(destRoute),
    sideName(originSide),sideName(destSide),originNodeAt(0).c_str());
  pulse(1,100,80,700);
}
bool encPressed=false,encLong=false,sosRaw=false,sosStable=false,sosTriggered=false;
unsigned long encChanged=0,encDownAt=0,sosChanged=0,sosPressedAt=0;
void serviceButtons() {
  noInterrupts();int steps=encoderSteps;encoderSteps=0;interrupts();
  while(steps>0){menuMove(1);steps--;}
  while(steps<0){menuMove(-1);steps++;}
  bool down=digitalRead(ENC_SW)==LOW;
  if(down!=encPressed && millis()-encChanged>35) {
    encChanged=millis();encPressed=down;
    if(down){encDownAt=millis();encLong=false;}
    else if(!encLong)encoderPress();
  }
  if(encPressed && !encLong && millis()-encDownAt>1200) {
    encLong=true;
    if(!help)resetJourney("encoder_long_press_reset");
  }
  // Debounce first; emit HELP_REQUEST only after a stable 3-second hold.
  down=digitalRead(SOS)==LOW;
  if(down!=sosRaw){sosRaw=down;sosChanged=millis();}
  if(millis()-sosChanged>=SOS_DEBOUNCE_MS && sosStable!=sosRaw){
    sosStable=sosRaw;
    if(sosStable){sosPressedAt=millis();sosTriggered=false;}
    else sosPressedAt=0;
  }
  if(sosStable && !sosTriggered && !help && millis()-sosPressedAt>=SOS_HOLD_MS){
    sosTriggered=true;help=true;changeState(EMERGENCY,"physical_help_button_long_press");
    event("HELP_REQUEST","physical_help_button_long_press");pulse(4,250,140,1600,HELP_ALERT);
  }
}

void checkpoint(String id,const char *source) {
  id.trim();id.toUpperCase();
  String expected;
  if(state==SEEK_PLATFORM && phase==TO_ORIGIN_PLATFORM){
    expected=originNodeAt(originProgress);
    if(id==expected){
      snprintf(lastCheckpoint,sizeof(lastCheckpoint),"%s",id.c_str());
      snprintf(lastStation,sizeof(lastStation),"DEMO_A");
      originProgress++;
      Serial.printf("CHECKPOINT %s source=%s next=%s\n",id.c_str(),source,
        originProgress<originNodeCount()?originNodeAt(originProgress).c_str():"WAIT_TRAIN");
      event("CHECKPOINT",source);pulse(1,100,70,800);
      if(originProgress==originNodeCount()){
        phase=AT_ORIGIN_PLATFORM;trainNear=false;
        changeState(WAIT_TRAIN,source);
        Serial.printf("WAIT_TRAIN at %s; expected train=TRAIN01 side=%s dest=%s\n",
          id.c_str(),sideName(originSide),destStationId());
      }
      return;
    }
  } else if(state==WAIT_TRAIN && phase==AT_ORIGIN_PLATFORM){
    expected="TRAIN_INSIDE";
    if(id==expected && boardingReady && !edge && !ultrasonicFault){
      snprintf(lastCheckpoint,sizeof(lastCheckpoint),"%s",id.c_str());
      phase=ONBOARD;doorOpen=false;trainStopped=false;boardingReady=false;trainNear=false;
      changeState(ON_TRAIN,source);
      event("BOARDING_CONFIRMED_BY_TAG",source);
      Serial.println("ON_TRAIN means cane reader reached the inside tag; body position is not independently proven");
      pulse(2,180,100,850);return;
    }
  } else if(state==ARRIVING && phase==VERIFY_DEST_PLATFORM){
    expected=destNodeAt(0);
    if(id==expected && destinationArrived && trainStopped && doorOpen && !edge && !ultrasonicFault){
      snprintf(lastCheckpoint,sizeof(lastCheckpoint),"%s",id.c_str());
      snprintf(lastStation,sizeof(lastStation),"%s",destStationId());
      phase=TO_DEST_EXIT;destProgress=1;
      Serial.printf("DESTINATION_PLATFORM_CONFIRMED %s next=%s\n",id.c_str(),destNodeAt(1).c_str());
      event("CHECKPOINT",source);pulse(2,120,80,900);return;
    }
  } else if(state==ARRIVING && phase==TO_DEST_EXIT){
    expected=destNodeAt(destProgress);
    if(id==expected){
      snprintf(lastCheckpoint,sizeof(lastCheckpoint),"%s",id.c_str());
      destProgress++;
      Serial.printf("CHECKPOINT %s source=%s next=%s\n",id.c_str(),source,
        destProgress<destNodeCount()?destNodeAt(destProgress).c_str():"COMPLETE");
      event("CHECKPOINT",source);pulse(1,100,70,800);
      if(destProgress==destNodeCount()){
        phase=DONE;changeState(COMPLETE,source);pulse(3,120,90,950);
      }
      return;
    }
  }
  if(id.equalsIgnoreCase(lastCheckpoint)){
    Serial.printf("CHECKPOINT_DUPLICATE %s ignored\n",id.c_str());return;
  }
  Serial.printf("CHECKPOINT_REJECTED got=%s expected=%s state=%s phase=%s\n",
    id.c_str(),expected.c_str(),stateName(state),phaseName(phase));
  event("CHECKPOINT_REJECTED",source);
}
void serviceRfid() {
  if(!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial())return;
  char uid[32]={0};
  for(byte i=0;i<rfid.uid.size && i<10;i++){
    char part[4];snprintf(part,sizeof(part),"%02X",rfid.uid.uidByte[i]);
    if(i)strcat(uid," ");strcat(uid,part);
  }
  const char *node=nullptr;
  if(strcmp(uid,"01 02 03 04")==0)node="A_MASUK";
  if(strcmp(uid,"11 22 33 44")==0)node="A_P1_WAIT";
  if(strcmp(uid,"55 66 77 88")==0)node="A_P2_WAIT";
  if(strcmp(uid,"AA BB CC DD")==0)node="TRAIN_INSIDE";
  if(strcmp(uid,"04 11 22 33 44 55 66")==0)node="B_P1_PERON";
  if(strcmp(uid,"C0 FF EE 99")==0)node="B_LUAR";
  if(node)checkpoint(String(node),"RFID_PHYSICAL");
  else Serial.printf("RFID_UNREGISTERED uid=%s\n",uid);
  rfid.PICC_HaltA();rfid.PCD_StopCrypto1();
}
void refreshBoardingReady(const char *source);
void serviceDistance() {
  if(millis()-lastDistance<120)return;
  lastDistance=millis();
  digitalWrite(TRIG,LOW);delayMicroseconds(2);digitalWrite(TRIG,HIGH);delayMicroseconds(10);digitalWrite(TRIG,LOW);
  unsigned long us=pulseIn(ECHO,HIGH,25000);
  if(!us){
    rawDistanceCm=NAN;distanceCm=NAN;edgeHits=0;edgeSafeSince=0;
    if(!ultrasonicFault){
      ultrasonicFault=true;event("EDGE_SENSOR_FAULT","HC_SR04");
      pulse(2,500,180,500,FAULT_ALERT);
      refreshBoardingReady("HC_SR04_FAULT");
    }
    return; // Do not clear a prior edge warning without a valid echo.
  }
  if(ultrasonicFault){ultrasonicFault=false;event("EDGE_SENSOR_RECOVERED","HC_SR04");refreshBoardingReady("HC_SR04_RECOVERED");}
  rawDistanceCm=us*0.0343f/2.0f;
  float correctedCm=correctedGroundDistanceCm(rawDistanceCm,tiltDeg);
  distanceRawFallback=!isfinite(correctedCm);
  distanceCm=distanceRawFallback?rawDistanceCm:correctedCm;
  if(!isfinite(rawBaseline))rawBaseline=rawDistanceCm;
  if(isfinite(correctedCm) && !isfinite(baseline))baseline=correctedCm;
  bool rawJump=rawDistanceCm>rawBaseline+15 && rawDistanceCm>25;
  bool correctedJump=isfinite(correctedCm) && correctedCm>baseline+15 && correctedCm>25;
  bool jump=distanceRawFallback?rawJump:correctedJump;
  edgeHits=jump?min(3,edgeHits+1):0;
  if(edgeHits>=3 && !edge){
    edge=true;edgeNeedsCorrectedClear=!distanceRawFallback;edgeSafeSince=0;
    event("EDGE_WARNING",distanceRawFallback?"HC_SR04_RAW_FALLBACK":"HC_SR04_MPU6050");
    if(state==WAIT_TRAIN || state==ARRIVING)Serial.println("EDGE_ADVISORY: pause and probe with the cane; gap width is not measured");
    pulse(1,700,100,1200,EDGE_ALERT);
    refreshBoardingReady("HC_SR04_EDGE");
  }
  // Keep separate baselines so switching between corrected and raw readings
  // does not compare values from different measurement modes.
  if(!rawJump)rawBaseline=rawBaseline*0.95f+rawDistanceCm*0.05f;
  if(isfinite(correctedCm) && !correctedJump)baseline=baseline*0.95f+correctedCm*0.05f;
  // A warning raised with corrected readings cannot be cleared solely by
  // raw fallback readings after the MPU fails.
  if(!jump && (!edgeNeedsCorrectedClear || !distanceRawFallback)){
    if(!edgeSafeSince)edgeSafeSince=millis();
    if(edge && millis()-edgeSafeSince>700){edge=false;edgeNeedsCorrectedClear=false;event("EDGE_CLEAR","HC_SR04");refreshBoardingReady("HC_SR04_EDGE_CLEAR");}
  } else edgeSafeSince=0;
}
void serviceMpu() {
  if(millis()-lastMpu<200)return;
  lastMpu=millis();Wire.beginTransmission(0x68);Wire.write(0x3B);
  if(Wire.endTransmission(false)!=0 || Wire.requestFrom(0x68,6,true)!=6){
    tiltDeg=NAN;tiltSince=0;tiltAlert=false;
    if(!mpuFault){mpuFault=true;event("MPU_FAULT_RAW_FALLBACK","MPU6050");pulse(2,500,180,500,FAULT_ALERT);}
    return;
  }
  if(mpuFault){mpuFault=false;event("MPU_RECOVERED","MPU6050");}
  int16_t ax=(Wire.read()<<8)|Wire.read(),ay=(Wire.read()<<8)|Wire.read(),az=(Wire.read()<<8)|Wire.read();
  tiltDeg=atan2f(sqrtf((float)ax*ax+(float)ay*ay),fabsf((float)az))*180.0f/PI;
  if(tiltDeg>65){
    if(!tiltSince)tiltSince=millis();
    if(!tiltAlert && millis()-tiltSince>2000){tiltAlert=true;event("CANE_TILT_ADVISORY","MPU6050");pulse(2,220,120,750);}
  }else{tiltSince=0;tiltAlert=false;}
}
void refreshBoardingReady(const char *source){
  bool ready=state==WAIT_TRAIN && trainNear && trainIdentityValid && trainStopped &&
    doorOpen && trainSide==originSide && !edge && !ultrasonicFault;
  if(ready==boardingReady)return;
  boardingReady=ready;
  if(ready){
    event("BOARDING_READY",source);
    Serial.println("BOARDING_READY: train data and local conditions align; still probe the platform gap with the cane");
    pulse(3,130,90,1000);
  }else{
    event("BOARDING_CANCELLED",source);
    Serial.println("BOARDING_CANCELLED: wait for fresh matching status before presenting TRAIN_INSIDE tag");
  }
}
void serviceBeacon() {
  if(millis()-lastBeacon<200)return;
  lastBeacon=millis();beaconRssiDbm=readDoorBeaconRSSI();
  bool near=state==WAIT_TRAIN && (trainNear?beaconRssiDbm>BEACON_FAR_DBM:beaconRssiDbm>BEACON_NEAR_DBM);
  if(near!=trainNear){
    trainNear=near;
    if(near){event("SIM_TRAIN_NEAR","POTENTIOMETER_BLE_STANDIN");Serial.println("TRAIN_NEAR is a simulated proximity cue, not train identity");pulse(2,100,100,900);}
    refreshBoardingReady("POTENTIOMETER_BLE_STANDIN");
  }
}
void serviceSerial() {
  while(Serial.available()){
    char c=(char)Serial.read();
    if(c=='\n'||c=='\r'){
      serialLine.trim();
      if(serialLine.length()){
        String cmd=serialLine;cmd.toUpperCase();
        if(cmd.startsWith("SIM TAG "))checkpoint(cmd.substring(8),"SERIAL_SIMULATION");
        else if(cmd.startsWith("SIM DEST ")){
          String chosen=cmd.substring(9);chosen.trim();
          if(state==SELECT_DEST && (chosen=="B" || chosen=="C")){
            destLetter=chosen[0];Serial.printf("MENU destination=%s; press encoder to confirm\n",destStationId());
          }else Serial.println("SIM DEST rejected: choose B or C before confirming route");
        }else if(cmd.startsWith("SIM CONFIG ")){
          char origin[12]={0},destination[12]={0},originPlatform[12]={0},destPlatform[12]={0};
          int fields=sscanf(cmd.c_str(),"SIM CONFIG %11s %11s %11s %11s",origin,destination,originPlatform,destPlatform);
          bool valid=fields==4 &&
            (!strcmp(origin,"FLAT") || !strcmp(origin,"LIFT") || !strcmp(origin,"RAMP")) &&
            (!strcmp(destination,"FLAT") || !strcmp(destination,"LIFT") || !strcmp(destination,"RAMP")) &&
            (!strcmp(originPlatform,"P1") || !strcmp(originPlatform,"P2")) &&
            (!strcmp(destPlatform,"P1") || !strcmp(destPlatform,"P2"));
          if(state==SELECT_DEST && valid){
            originRoute=!strcmp(origin,"LIFT")?LIFT_ROUTE:!strcmp(origin,"RAMP")?RAMP_ROUTE:FLAT_ROUTE;
            destRoute=!strcmp(destination,"LIFT")?LIFT_ROUTE:!strcmp(destination,"RAMP")?RAMP_ROUTE:FLAT_ROUTE;
            originSide=!strcmp(originPlatform,"P2")?P2:P1;
            destSide=!strcmp(destPlatform,"P2")?P2:P1;
            Serial.printf("MAP origin=%s exit=%s platforms=%s/%s; press encoder to confirm\n",
              routeName(originRoute),routeName(destRoute),sideName(originSide),sideName(destSide));
          }else Serial.println("SIM CONFIG rejected: use SIM CONFIG FLAT|LIFT|RAMP FLAT|LIFT|RAMP P1|P2 P1|P2 before route selection");
        }else if(cmd.startsWith("SIM TRAIN ")){
          char train[12]={0},side[12]={0},destination[12]={0};
          int fields=sscanf(cmd.c_str(),"SIM TRAIN %11s %11s %11s",train,side,destination);
          if(state==WAIT_TRAIN && fields==3){
            trainIdentityValid=!strcmp(train,"TRAIN01") &&
              !strcmp(side,sideName(originSide)) && destination[0]==destLetter && destination[1]==0;
            trainStopped=false;doorOpen=false;
            if(trainIdentityValid){
              trainSide=originSide;event("TRAIN_MATCH","SERIAL_TRAIN_SIMULATION");
              Serial.printf("TRAIN_MATCH %s side=%s destination=%s; await STOPPED and DOOR OPEN\n",train,side,destination);
            }else{
              event("TRAIN_REJECTED","SERIAL_TRAIN_SIMULATION");
              Serial.printf("TRAIN_REJECTED got=%s/%s/%s expected=TRAIN01/%s/%c\n",
                train,side,destination,sideName(originSide),destLetter);
            }
            refreshBoardingReady("SERIAL_TRAIN_SIMULATION");
          }else Serial.println("SIM TRAIN rejected: use SIM TRAIN TRAIN01 P1|P2 B|C in WAIT_TRAIN");
        }else if(cmd=="SIM STOPPED"){
          if((state==WAIT_TRAIN && trainIdentityValid) || (state==ARRIVING && destinationArrived)){
            trainStopped=true;event("TRAIN_STOPPED","SERIAL_TRAIN_SIMULATION");
            refreshBoardingReady("SERIAL_TRAIN_SIMULATION");
          }else Serial.println("SIM STOPPED rejected: no matched train or arrival");
        }else if(cmd=="SIM MOVING"){
          if(state==WAIT_TRAIN || state==ARRIVING || state==ON_TRAIN){
            trainStopped=false;doorOpen=false;event("TRAIN_MOVING","SERIAL_TRAIN_SIMULATION");
            refreshBoardingReady("SERIAL_TRAIN_SIMULATION");
          }else Serial.println("SIM MOVING ignored outside train journey");
        }else if(cmd.startsWith("SIM DOOR ")){
          char action[12]={0},side[12]={0};
          int fields=sscanf(cmd.c_str(),"SIM DOOR %11s %11s",action,side);
          bool open=!strcmp(action,"OPEN"),close=!strcmp(action,"CLOSE");
          bool originDoor=state==WAIT_TRAIN && trainIdentityValid && !strcmp(side,sideName(originSide));
          bool destDoor=state==ARRIVING && destinationArrived && !strcmp(side,sideName(destSide));
          if(fields==2 && (open || close) && (originDoor || destDoor) && (!open || trainStopped)){
            doorOpen=open;
            event(open?"TRAIN_DOOR_OPEN":"TRAIN_DOOR_CLOSED","SERIAL_TRAIN_SIMULATION");
            refreshBoardingReady("SERIAL_TRAIN_SIMULATION");
          }else Serial.println("SIM DOOR rejected: side/state must match and train must be stopped before OPEN");
        }else if(cmd.startsWith("SIM ARRIVE ")){
          String arrival=cmd.substring(11);arrival.trim();
          if(state==ON_TRAIN && arrival.length()==1 && arrival[0]==destLetter){
            destinationArrived=true;trainStopped=false;doorOpen=false;
            phase=VERIFY_DEST_PLATFORM;
            changeState(ARRIVING,"SERIAL_TRAIN_SIMULATION");
            event("SIM_DESTINATION_APPROACH","SERIAL_TRAIN_SIMULATION");
            Serial.printf("ARRIVING %s; await SIM STOPPED, SIM DOOR OPEN %s, and destination platform tag\n",
              destStationId(),sideName(destSide));
            pulse(3,180,100,1100);
          }else Serial.println("SIM ARRIVE rejected: must be ON_TRAIN and match selected destination");
        }else if(cmd=="ACK HELP" && help){
          help=false;resetJourney("SERIAL_DEMO_RESET");
          Serial.println("HELP ACK is demo reset only; not proof assistance arrived");
        }else if(cmd=="STATUS")lastStatus=millis()-5000UL;
        else if(cmd=="HELP")Serial.println("SIM CONFIG <origin FLAT|LIFT|RAMP> <exit FLAT|LIFT|RAMP> <origin P1|P2> <dest P1|P2> | SIM DEST B|C | SIM TAG <node> | SIM TRAIN TRAIN01 P1|P2 B|C | SIM STOPPED | SIM MOVING | SIM DOOR OPEN|CLOSE P1|P2 | SIM ARRIVE B|C | ACK HELP | STATUS");
        else Serial.println("Unknown command; type HELP");
      }
      serialLine="";
    }else if(serialLine.length()<96)serialLine+=c;
  }
}

// Network operations stay on core 0. The local sensor/alert loop only uses
// queueMqttJson(...), which has a zero-tick timeout.
void mqttTask(void *){
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID,WIFI_PASSWORD,6);
  WiFiClientSecure network;
  network.setInsecure(); // Wokwi demo; a physical device must verify the broker certificate.
  PubSubClient mqtt(network);
  mqtt.setServer(MQTT_HOST,MQTT_PORT);
  if(!mqtt.setBufferSize(384)){
    Serial.println("MQTT buffer allocation failed; local alerts remain active");
    vTaskDelete(nullptr);
    return;
  }
  mqtt.setSocketTimeout(5);
  mqtt.setKeepAlive(30);

  MqttTxMessage message{};
  unsigned long lastWifiTry=millis();
  unsigned long lastMqttTry=millis()-5000UL;
  for(;;){
    if(WiFi.status()!=WL_CONNECTED){
      mqttReady.store(false);
      while(xQueueReceive(mqttQueue,&message,0)==pdTRUE)mqttDropped.fetch_add(1);
      if(mqtt.connected())mqtt.disconnect();
      if(millis()-lastWifiTry>=15000UL){lastWifiTry=millis();WiFi.reconnect();}
      vTaskDelay(pdMS_TO_TICKS(50));
      continue;
    }
    if(!mqtt.connected()){
      mqttReady.store(false);
      while(xQueueReceive(mqttQueue,&message,0)==pdTRUE)mqttDropped.fetch_add(1);
      if(millis()-lastMqttTry>=5000UL){
        lastMqttTry=millis();
        if(mqtt.connect(MQTT_CLIENT_ID,nullptr,nullptr,
                        MQTT_ONLINE_TOPIC,1,true,"0")){
          if(mqtt.publish(MQTT_ONLINE_TOPIC,"1",true)){
            mqttReady.store(true);
            Serial.println("MQTT connected; QoS 0 publishes enabled");
          }else mqtt.disconnect();
        }
      }
      vTaskDelay(pdMS_TO_TICKS(50));
      continue;
    }
    if(!mqtt.loop())mqttReady.store(false);
    if(mqttReady.load() && xQueueReceive(mqttQueue,&message,0)==pdTRUE){
      const char *topic=message.kind==MqttTxKind::Event?MQTT_EVENTS_TOPIC:MQTT_STATUS_TOPIC;
      if(!mqtt.publish(topic,message.json)){
        mqttDropped.fetch_add(1);
        mqttReady.store(false);
        mqtt.disconnect();
      }
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void startMqttTask(){
  mqttQueue=xQueueCreate(8,sizeof(MqttTxMessage));
  if(!mqttQueue){Serial.println("MQTT queue allocation failed; local alerts remain active");return;}
  if(xTaskCreatePinnedToCore(mqttTask,"mqtt",16384,nullptr,1,nullptr,0)!=pdPASS){
    vQueueDelete(mqttQueue);
    mqttQueue=nullptr;
    Serial.println("MQTT task start failed; local alerts remain active");
  }
}

void setup(){
  Serial.begin(115200);
  pinMode(TRIG,OUTPUT);pinMode(ECHO,INPUT);
  pinMode(ENC_CLK,INPUT_PULLUP);pinMode(ENC_DT,INPUT_PULLUP);pinMode(ENC_SW,INPUT_PULLUP);
  pinMode(SOS,INPUT_PULLUP);pinMode(BUZZ,OUTPUT);pinMode(LED_GETAR,OUTPUT);
  Wire.begin(SDA_MPU,SCL_MPU);Wire.beginTransmission(0x68);Wire.write(0x6B);Wire.write(0);Wire.endTransmission();
  SPI.begin(18,19,23,RFID_SS);rfid.PCD_Init();
  attachInterrupt(digitalPinToInterrupt(ENC_CLK),encoderTick,FALLING);
  Serial.println("SIC8 fictional station journey | C1 pin map | MQTT outbound demo");
  Serial.println("Potentiometer stands in for BLE proximity; serial commands stand in for train telemetry");
  Serial.println("SOS: hold button about 3 s; edge distance corrected with MPU tilt");
  Serial.println("MENU destination B/C: rotate, short press to confirm; long press to reset");
  Serial.println("Type HELP for simulation commands");
  startMqttTask();
}
void loop(){
  uint32_t startedUs=micros();
  serviceSerial();serviceButtons();serviceRfid();serviceMpu();serviceDistance();serviceBeacon();servicePulse();
  queueMqttStatus();
  if(millis()-lastStatus>=5000){
    lastStatus=millis();
    String next="";
    if(state==SEEK_PLATFORM)next=originNodeAt(originProgress);
    else if(state==WAIT_TRAIN)next="TRAIN_INSIDE (after matching train, STOPPED, DOOR OPEN, near cue)";
    else if(state==ON_TRAIN)next=String("SIM ARRIVE ")+destLetter;
    else if(state==ARRIVING)next=destNodeAt(destProgress);
    Serial.printf("\n[STATUS] %s phase=%s destination=%s next=%s\n",
      stateName(state),phaseName(phase),destStationId(),next.c_str());
    Serial.printf("  Map: origin=%s exit=%s platform=%s/%s checkpoint=%s\n",
      routeName(originRoute),routeName(destRoute),sideName(originSide),sideName(destSide),lastCheckpoint);
    if(isfinite(distanceCm))Serial.printf("  Jarak bawah: %.0f cm (%s)\n",distanceCm,distanceRawFallback?"HC-SR04 mentah; koreksi tidak tersedia":"koreksi MPU");
    else Serial.println("  Jarak bawah: tidak tersedia (HC-SR04 gagal)");
    if(isfinite(tiltDeg))Serial.printf("  Miring: %.0f derajat\n",tiltDeg);
    else Serial.println("  Miring: pembacaan MPU tidak tersedia");
    Serial.printf("  Tepi: %s\n",edge?"PERINGATAN":(ultrasonicFault?"sensor gagal; kewaspadaan diperlukan":(distanceRawFallback?"pemantauan cadangan; bukan jaminan aman":"tidak ada peringatan")));
    if(state==WAIT_TRAIN || state==ARRIVING)Serial.printf("  Train: near=%d identity=%d stopped=%d door_open=%d boarding_ready=%d; beacon_sim=%.0f dBm\n",
      trainNear,trainIdentityValid,trainStopped,doorOpen,boardingReady,beaconRssiDbm);
    if(help)Serial.println("  Bantuan: permintaan lokal aktif");
    Serial.printf("  MQTT: %s; drop=%lu; loopMaxMs=%.2f\n",
      mqttReady.load()?"connected":"offline",(unsigned long)mqttDropped.load(),loopMaxUs/1000.0f);
    loopMaxUs=0;
  }
  uint32_t elapsedUs=micros()-startedUs;
  if(elapsedUs>loopMaxUs)loopMaxUs=elapsedUs;
}
