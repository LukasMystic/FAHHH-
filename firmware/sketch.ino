#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <MFRC522.h>
#include <math.h>

// Pin dibaca dari diagram.json proyek ini, 26 Okt 2026.
// Versi C1: beacon dan kedatangan kereta tetap SIMULASI.
// Asumsi koreksi jarak: pancaran HC-SR04 sejajar sumbu tongkat/MPU.
// Orientasi pemasangan nyata perlu dikalibrasi sebelum dipakai di luar demo.
const int TRIG=26, ECHO=27, SDA_MPU=21, SCL_MPU=22;
const int RFID_SS=5, RFID_RST=4, ENC_CLK=32, ENC_DT=33, ENC_SW=25;
const int SOS=13, BUZZ=14, LED_GETAR=17, BEACON=34;
MFRC522 rfid(RFID_SS, RFID_RST);

enum State { SELECT_LINE, SELECT_DEST, SEEK_PLATFORM, WAIT_TRAIN, ON_TRAIN, ARRIVING, COMPLETE, EMERGENCY };
State state=SELECT_LINE;
struct Station { const char *id; const char *name; };
const Station A[]={{"A01","Jakarta Kota"},{"A02","Jayakarta"},{"A03","Mangga Besar"},{"A04","Sawah Besar"},{"A05","Juanda"},{"A06","Gondangdia"}};
const Station B[]={{"B01","Tanah Abang"},{"B02","Palmerah"},{"B03","Kebayoran"},{"B04","Pondok Ranji"}};
const Station *LINES[]={A,B};
const int LENGTH[]={6,4};
const char *LINE_NAME[]={"Demo A","Demo B"};
int lineNo=0, destNo=0, currentNo=-1;
bool trainNear=false, serialTrain=false, edge=false, tiltAlert=false, help=false;
float rawDistanceCm=NAN, distanceCm=NAN, baseline=NAN, tiltDeg=NAN;
float beaconRssiDbm=NAN;
int beaconAdc=0, edgeHits=0;
unsigned long lastDistance=0,lastMpu=0,lastBeacon=0,lastStatus=0,edgeSafeSince=0,tiltSince=0;
String serialLine;

constexpr unsigned long SOS_HOLD_MS=3000;
constexpr unsigned long SOS_DEBOUNCE_MS=40;
constexpr float MAX_EDGE_TILT_DEG=65.0f;
// Nilai ekuivalen dari ambang ADC demo sebelumnya: masuk >2600, keluar <=2100.
constexpr float BEACON_NEAR_DBM=-100.0f+2600.0f*60.0f/4095.0f;
constexpr float BEACON_FAR_DBM=-100.0f+2100.0f*60.0f/4095.0f;

// Pada Wokwi, potensiometer 0..4095 mewakili RSSI -100..-40 dBm.
<<<<<<< Updated upstream
// Pada alat nyata, ganti isi fungsi ini dengan hasil pemindaian BLE.
float readDoorBeaconRSSI() {
  beaconAdc=analogRead(BEACON);
  return -100.0f+beaconAdc*60.0f/4095.0f;
}

// Proyeksi jarak miring ke tinggi vertikal. Sudut yang terlalu besar atau
// pembacaan MPU yang hilang membuat hasil tidak layak untuk deteksi tepi.
float correctedGroundDistanceCm(float measuredCm,float caneTiltDeg) {
  if(!isfinite(measuredCm) || !isfinite(caneTiltDeg) || caneTiltDeg>MAX_EDGE_TILT_DEG)return NAN;
  return measuredCm*cosf(caneTiltDeg*PI/180.0f);
}

const char *stateName(State s) {
  switch(s) {
    case SELECT_LINE:return "SELECT_LINE"; case SELECT_DEST:return "SELECT_DEST";
    case SEEK_PLATFORM:return "SEEK_PLATFORM"; case WAIT_TRAIN:return "WAIT_TRAIN";
    case ON_TRAIN:return "ON_TRAIN"; case ARRIVING:return "ARRIVING";
    case COMPLETE:return "COMPLETE"; default:return "EMERGENCY";
  }
}
void event(const char *name,const char *source) {
  Serial.printf("EVENT t=%lu event=%s state=%s source=%s distance_cm=%.1f beacon_adc=%d\n",millis(),name,stateName(state),source,distanceCm,beaconAdc);
}
void changeState(State next,const char *source) {
  if(state==next)return;
  Serial.printf("STATE %s -> %s source=%s\n",stateName(state),stateName(next),source);
  state=next; event(stateName(next),source);
}

// Bunyi dan LED tanpa delay panjang.
struct Pattern { int count,onMs,offMs,hz,step; unsigned long next; } pat={0,0,0,0,0,0};
void pulse(int count,int onMs,int offMs,int hz) {
  if(help && hz!=1600)return;
  pat={count,onMs,offMs,hz,0,millis()};
}
void servicePulse() {
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
  if(state==SELECT_LINE) {
    lineNo=(lineNo+2+dir)%2;
    Serial.printf("MENU line=%s (%d/2)\n",LINE_NAME[lineNo],lineNo+1);
  } else if(state==SELECT_DEST) {
    destNo=(destNo+LENGTH[lineNo]+dir)%LENGTH[lineNo];
    Serial.printf("MENU destination=%s %s (%d/%d)\n",LINES[lineNo][destNo].id,LINES[lineNo][destNo].name,destNo+1,LENGTH[lineNo]);
  }
  pulse(1,45,50,650);
}
=======
  // Pada alat nyata, ganti isi fungsi ini dengan hasil pemindaian BLE.
  float readDoorBeaconRSSI() {
    beaconAdc=analogRead(BEACON);
    return -100.0f+beaconAdc*60.0f/4095.0f;
  }

// Proyeksi jarak miring ke tinggi vertikal. Sudut yang terlalu besar atau
// pembacaan MPU yang hilang membuat hasil tidak layak untuk deteksi tepi.
float correctedGroundDistanceCm(float measuredCm,float caneTiltDeg) {
  if(!isfinite(measuredCm) || !isfinite(caneTiltDeg) || caneTiltDeg>MAX_EDGE_TILT_DEG)return NAN;
  return measuredCm*cosf(caneTiltDeg*PI/180.0f);
}

const char *stateName(State s) {
  switch(s) {
    case SELECT_LINE:return "SELECT_LINE"; case SELECT_DEST:return "SELECT_DEST";
    case SEEK_PLATFORM:return "SEEK_PLATFORM"; case WAIT_TRAIN:return "WAIT_TRAIN";
    case ON_TRAIN:return "ON_TRAIN"; case ARRIVING:return "ARRIVING";
    case COMPLETE:return "COMPLETE"; default:return "EMERGENCY";
  }
}
void event(const char *name,const char *source) {
  Serial.printf("EVENT t=%lu event=%s state=%s source=%s distance_cm=%.1f beacon_adc=%d\n",millis(),name,stateName(state),source,distanceCm,beaconAdc);
}
void changeState(State next,const char *source) {
  if(state==next)return;
  Serial.printf("STATE %s -> %s source=%s\n",stateName(state),stateName(next),source);
  state=next; event(stateName(next),source);
}

// Bunyi dan LED tanpa delay panjang.
struct Pattern { int count,onMs,offMs,hz,step; unsigned long next; } pat={0,0,0,0,0,0};
void pulse(int count,int onMs,int offMs,int hz) {
  if(help && hz!=1600)return;
  pat={count,onMs,offMs,hz,0,millis()};
}
void servicePulse() {
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
  if(state==SELECT_LINE) {
    lineNo=(lineNo+2+dir)%2;
    Serial.printf("MENU line=%s (%d/2)\n",LINE_NAME[lineNo],lineNo+1);
  } else if(state==SELECT_DEST) {
    destNo=(destNo+LENGTH[lineNo]+dir)%LENGTH[lineNo];
    Serial.printf("MENU destination=%s %s (%d/%d)\n",LINES[lineNo][destNo].id,LINES[lineNo][destNo].name,destNo+1,LENGTH[lineNo]);
  }
  pulse(1,45,50,650);
}
>>>>>>> Stashed changes
void encoderPress() {
  if(state==SELECT_LINE) {
    destNo=0;changeState(SELECT_DEST,"encoder_button");
    Serial.printf("MENU destination=%s %s\n",LINES[lineNo][0].id,LINES[lineNo][0].name);
  } else if(state==SELECT_DEST) {
    currentNo=-1;changeState(SEEK_PLATFORM,"encoder_button");
    Serial.printf("ROUTE destination=%s %s; RFID checkpoint required\n",LINES[lineNo][destNo].id,LINES[lineNo][destNo].name);
  } else if(state==WAIT_TRAIN && trainNear) {
    changeState(ON_TRAIN,"user_confirmed_boarding");
    event("BOARDING_CONFIRMED_BY_USER","encoder_button");pulse(2,180,100,850);
  } else if(state==ARRIVING) {
    changeState(COMPLETE,"user_confirmed_alighting");
    event("ALIGHTING_CONFIRMED_BY_USER","encoder_button");pulse(3,120,90,950);
  }
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
    if(!help){changeState(SELECT_LINE,"encoder_long_press_reset");lineNo=0;destNo=0;serialTrain=false;}
  }
  // Debounce lebih dulu; HELP_REQUEST hanya aktif setelah tombol ditahan 3 s.
  down=digitalRead(SOS)==LOW;
  if(down!=sosRaw){sosRaw=down;sosChanged=millis();}
  if(millis()-sosChanged>=SOS_DEBOUNCE_MS && sosStable!=sosRaw){
    sosStable=sosRaw;
    if(sosStable){sosPressedAt=millis();sosTriggered=false;}
    else sosPressedAt=0;
  }
  if(sosStable && !sosTriggered && !help && millis()-sosPressedAt>=SOS_HOLD_MS){
    sosTriggered=true;help=true;changeState(EMERGENCY,"physical_help_button_long_press");
    event("HELP_REQUEST","physical_help_button_long_press");pulse(4,250,140,1600);
  }
}

void checkpoint(String id,const char *source) {
  int found=-1;
  for(int i=0;i<LENGTH[lineNo];i++)if(id.equalsIgnoreCase(LINES[lineNo][i].id))found=i;
  if(found<0){Serial.printf("RFID_UNKNOWN id=%s source=%s\n",id.c_str(),source);return;}
  currentNo=found;
  Serial.printf("RFID_CHECKPOINT id=%s name=%s source=%s\n",LINES[lineNo][found].id,LINES[lineNo][found].name,source);
  event("CHECKPOINT",source);
  if(state==SEEK_PLATFORM) {
    if(found==destNo){changeState(COMPLETE,"destination_checkpoint");pulse(3,120,90,950);}
    else {
      Serial.printf("PLATFORM_GUIDANCE DEMO line=%s direction=%s; verify signs and staff\n",LINE_NAME[lineNo],found<destNo?"increasing_station_index":"decreasing_station_index");
      changeState(WAIT_TRAIN,source);pulse(2,100,100,700);
    }
  } else if(state==ON_TRAIN && found==destNo) {
    Serial.println("NOTE destination RFID on train is a demo signal, not live train positioning");
    changeState(ARRIVING,source);pulse(3,180,100,1100);
  }
}
void serviceRfid() {
  if(!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial())return;
  char uid[32]={0};
  for(byte i=0;i<rfid.uid.size && i<10;i++){
    char part[4];snprintf(part,sizeof(part),"%02X",rfid.uid.uidByte[i]);
    if(i)strcat(uid," ");strcat(uid,part);
  }
  const char *station=nullptr;
  if(strcmp(uid,"01 02 03 04")==0)station="A01"; // kartu biru Wokwi
  if(strcmp(uid,"11 22 33 44")==0)station="A03"; // hijau
  if(strcmp(uid,"55 66 77 88")==0)station="A06"; // kuning
  if(strcmp(uid,"AA BB CC DD")==0)station="B01"; // merah
  if(strcmp(uid,"C0 FF EE 99")==0)station="B04"; // key fob
  if(station)checkpoint(String(station),"RFID_PHYSICAL");
  else Serial.printf("RFID_UNREGISTERED uid=%s\n",uid);
  rfid.PICC_HaltA();rfid.PCD_StopCrypto1();
}
void serviceDistance() {
  if(millis()-lastDistance<120)return;
  lastDistance=millis();
  digitalWrite(TRIG,LOW);delayMicroseconds(2);digitalWrite(TRIG,HIGH);delayMicroseconds(10);digitalWrite(TRIG,LOW);
  unsigned long us=pulseIn(ECHO,HIGH,25000);
  if(!us){
    rawDistanceCm=NAN;distanceCm=NAN;edgeHits=0;edgeSafeSince=0;
    Serial.println("SENSOR ultrasonic=NO_ECHO");return;
  }
  rawDistanceCm=us*0.0343f/2.0f;
  distanceCm=correctedGroundDistanceCm(rawDistanceCm,tiltDeg);
  if(!isfinite(distanceCm)){
    edgeHits=0;edgeSafeSince=0;
    return; // pertahankan peringatan lama sampai pengukuran valid kembali
  }
  if(baseline!=baseline)baseline=distanceCm;
  bool jump=distanceCm>baseline+15 && distanceCm>25;
  edgeHits=jump?min(3,edgeHits+1):0;
  if(edgeHits>=3 && !edge){edge=true;edgeSafeSince=0;event("EDGE_WARNING","HC_SR04");pulse(1,700,100,1200);}
  if(!jump){
    if(!edgeSafeSince)edgeSafeSince=millis();
    if(edge && millis()-edgeSafeSince>700){edge=false;event("EDGE_CLEAR","HC_SR04");}
    baseline=baseline*0.95f+distanceCm*0.05f;
  } else edgeSafeSince=0;
}
void serviceMpu() {
  if(millis()-lastMpu<200)return;
  lastMpu=millis();Wire.beginTransmission(0x68);Wire.write(0x3B);
  if(Wire.endTransmission(false)!=0 || Wire.requestFrom(0x68,6,true)!=6){tiltDeg=NAN;return;}
  int16_t ax=(Wire.read()<<8)|Wire.read(),ay=(Wire.read()<<8)|Wire.read(),az=(Wire.read()<<8)|Wire.read();
  tiltDeg=atan2f(sqrtf((float)ax*ax+(float)ay*ay),fabsf((float)az))*180.0f/PI;
  if(tiltDeg>65){
    if(!tiltSince)tiltSince=millis();
    if(!tiltAlert && millis()-tiltSince>2000){tiltAlert=true;event("CANE_TILT_ADVISORY","MPU6050");pulse(2,220,120,750);}
  }else{tiltSince=0;tiltAlert=false;}
}
void serviceBeacon() {
  if(millis()-lastBeacon<200)return;
  lastBeacon=millis();beaconRssiDbm=readDoorBeaconRSSI();
  bool near=serialTrain || (trainNear?beaconRssiDbm>BEACON_FAR_DBM:beaconRssiDbm>BEACON_NEAR_DBM);
  if(near!=trainNear){
    trainNear=near;
    if(state==WAIT_TRAIN && near){event("SIM_TRAIN_NEAR","POTENTIOMETER_BLE_STANDIN");Serial.println("BOARDING_CUE DEMO: verify line/direction, press encoder after boarding");pulse(3,100,100,900);}
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
        else if(cmd=="SIM TRAIN"){serialTrain=true;trainNear=true;event("SIM_TRAIN_NEAR","SERIAL_SIMULATION");}
        else if(cmd.startsWith("SIM ARRIVE ")){
          String id=cmd.substring(11);
          if(state==ON_TRAIN && id.equalsIgnoreCase(LINES[lineNo][destNo].id)){
            changeState(ARRIVING,"SERIAL_SIMULATED_TRAIN_TELEMETRY");
            event("SIM_DESTINATION_APPROACH","SERIAL_SIMULATED_TRAIN_TELEMETRY");pulse(3,180,100,1100);
          }else Serial.println("SIM ARRIVE ignored: must be ON_TRAIN and match destination");
        }else if(cmd=="ACK HELP" && help){help=false;changeState(SELECT_LINE,"SERIAL_DEMO_RESET");Serial.println("HELP ACK is demo reset only; not proof assistance arrived");}
        else if(cmd=="STATUS")lastStatus=0;
        else Serial.println("Commands: SIM TAG A01 | SIM TRAIN | SIM ARRIVE A06 | ACK HELP | STATUS");
      }
      serialLine="";
    }else if(serialLine.length()<64)serialLine+=c;
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
  Serial.println("SIC8 Role3 boot | WOKWI PIN MAP VERIFIED | OFFLINE FIRST | DEMO ROUTES");
  Serial.println("SIM labels: potentiometer stands in for BLE; Serial SIM ARRIVE stands in for train telemetry");
  Serial.println("SOS: hold button about 3 s; edge distance corrected with MPU tilt");
  Serial.println("MENU line=Demo A (1/2); rotate, short press to select; long press to reset");
}
void loop(){
  serviceSerial();serviceButtons();serviceRfid();serviceMpu();serviceDistance();serviceBeacon();servicePulse();
  if(millis()-lastStatus>=5000){
    lastStatus=millis();
    Serial.printf("\n[STATUS] %s | %s (%s)\n",stateName(state),LINES[lineNo][destNo].name,LINES[lineNo][destNo].id);
    if(isfinite(distanceCm))Serial.printf("  Jarak bawah (koreksi MPU): %.0f cm\n",distanceCm);
    else Serial.println("  Jarak bawah: tidak valid (cek MPU/sudut/ultrasonik)");
    if(isfinite(tiltDeg))Serial.printf("  Miring: %.0f derajat\n",tiltDeg);
    else Serial.println("  Miring: pembacaan MPU tidak tersedia");
    Serial.printf("  Tepi: %s\n",edge?"PERINGATAN":(isfinite(distanceCm)?"tidak ada peringatan":"sensor belum bisa menilai"));
    if(state==WAIT_TRAIN)Serial.printf("  Beacon (SIM): %.0f dBm; kereta %s\n",beaconRssiDbm,trainNear?"dekat":"belum dekat");
    if(help)Serial.println("  Bantuan: permintaan lokal aktif");
  }
}
