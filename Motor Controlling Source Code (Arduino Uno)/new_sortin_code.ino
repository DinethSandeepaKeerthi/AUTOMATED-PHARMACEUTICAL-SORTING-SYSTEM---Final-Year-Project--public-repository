#include <Servo.h>

// Pin Definitions
const int VIBRATOR_PIN1 = 0;
const int PC_FW_LIMIT = 1;
const int CONVEYOR_PIN1 = 2;
const int PC_BW_LIMIT = 3;
const int ROTOR_PIN1 = 4;
const int ROTOR_PIN2 = 7;
const int SERVO1_PIN = 5;
const int SERVO2_PIN = 6;
const int P_CHANGER_PIN1 = 8;
const int P_CHANGER_PIN2 = 9;
const int SERVO3_PIN = 10;            // Servo controlled by GRBL spindle PWM
const int GRBL_PWM_INPUT = 11;        // Input pin from GRBL spindle PWM
const int TPUSH_PIN1 = 12;
const int COM_LOW_PIN = 13;

// Input Pins
const int VIBRATOR_INPUT = A0;
const int TPUSH_INPUT = A1;
const int CONVEYOR_INPUT = A2;
const int CONTROL_INPUT1 = A3;
const int CONTROL_INPUT2 = A4;
const int CONTROL_INPUT3 = A5;

// Servo Instances
Servo servo1;
Servo servo2;
Servo servo3;  // Controlled by GRBL PWM

const int stepsPerRevolution = 50;

void setup() {
  pinMode(VIBRATOR_PIN1, OUTPUT);
  pinMode(CONVEYOR_PIN1, OUTPUT);
  pinMode(ROTOR_PIN1, OUTPUT);
  pinMode(ROTOR_PIN2, OUTPUT);
  pinMode(TPUSH_PIN1, OUTPUT);
  pinMode(COM_LOW_PIN, OUTPUT);
  pinMode(P_CHANGER_PIN1, OUTPUT);
  pinMode(P_CHANGER_PIN2, OUTPUT);

  pinMode(VIBRATOR_INPUT, INPUT);
  pinMode(TPUSH_INPUT, INPUT);
  pinMode(CONVEYOR_INPUT, INPUT);
  pinMode(CONTROL_INPUT1, INPUT);
  pinMode(CONTROL_INPUT2, INPUT);
  pinMode(CONTROL_INPUT3, INPUT);
  pinMode(GRBL_PWM_INPUT, INPUT);
  pinMode(PC_FW_LIMIT, INPUT);
  pinMode(PC_BW_LIMIT, INPUT);

  servo1.attach(SERVO1_PIN);
  servo2.attach(SERVO2_PIN);
  servo3.attach(SERVO3_PIN);  // Attach the third servo
}

void loop() {
  int pcfwlimit = digitalRead(PC_FW_LIMIT);
  int pcbwlimit = digitalRead(PC_BW_LIMIT);
  int vibratorInput = digitalRead(VIBRATOR_INPUT);
  int tpushInput = digitalRead(TPUSH_INPUT);
  int conveyorInput = digitalRead(CONVEYOR_INPUT);
  int control1 = digitalRead(CONTROL_INPUT1);
  int control2 = digitalRead(CONTROL_INPUT2);
  int control3 = digitalRead(CONTROL_INPUT3);

  if (vibratorInput == LOW ) {
    controlVibrator();
  } else {
    digitalWrite(VIBRATOR_PIN1, LOW);
    digitalWrite(COM_LOW_PIN, LOW);
  }

  if (tpushInput == LOW) {
    controlTpush();
  } else {
    digitalWrite(TPUSH_PIN1, LOW);
    digitalWrite(COM_LOW_PIN, LOW);
  }

  if (conveyorInput == LOW) {
    controlConveyor();
  } else {
    digitalWrite(CONVEYOR_PIN1, LOW);
    digitalWrite(COM_LOW_PIN, LOW);
  }

  //int command = (control1 << 2) | (control2 << 1) | control3;
  //controlMotorFunctions(command);

// NEW ADDED

// Count active (HIGH) signals
int activeCount = control1 + control2 + control3;

if (activeCount == 1) {
  if (control1 == HIGH) {
    stopRotor();
    pathchanger(true);
  } else if (control2 == HIGH) {
    stopRotor();
    stoppathchanger();
    moveServos(45);
  } else if (control3 == HIGH) {
    stopRotor();
    stoppathchanger();
    moveServos(-45);
  }

} else if (activeCount == 2) {
  if (control1 == LOW) {
    stoppathchanger();
    rotateRotor(true);  // Only control2 and control3 are HIGH
  } else if (control2 == LOW) {
    stoppathchanger();
    rotateRotor(false); // Only control1 and control3 are HIGH
  } else if (control3 == LOW) {
    stopRotor();
    pathchanger(false); // Only control1 and control2 are HIGH
  }

} else if (activeCount == 3) {
  stopRotor();

} else {
  // No control signal active – stop everything for safety
  stopRotor();
  stoppathchanger();
  
}



  // GRBL PWM to servo3 control (non-blocking)
  updateServoFromPWM();

  
}


// === GRBL spindle PWM input read and map to servo3 ===
void updateServoFromPWM() {
  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate >= 20) { // Update ~50Hz
    lastUpdate = millis();

    int pwmWidth = pulseIn(GRBL_PWM_INPUT, HIGH, 25000);  // Max wait ~25ms

    if (pwmWidth > 0) {
      int angle = map(pwmWidth, 0, 500, 0, 180);
      angle = constrain(angle, 0, 180);
      servo3.write(angle);
    }
  }
}

void controlVibrator() {
  digitalWrite(VIBRATOR_PIN1, HIGH);
  digitalWrite(COM_LOW_PIN, LOW);
}

void controlTpush() {
  digitalWrite(TPUSH_PIN1, HIGH);
  digitalWrite(COM_LOW_PIN, LOW);
}

void controlConveyor() {
  digitalWrite(CONVEYOR_PIN1, HIGH);
  digitalWrite(COM_LOW_PIN, LOW);
}

void controlMotorFunctions(int command) {
  switch (command) {
    case 0b111:
      stopRotor();
      break;
    case 0b110:
      rotateRotor(true);
      break;
    case 0b101:
      rotateRotor(false);
      break;
    case 0b100:
      pathchanger(true);
      break;
    case 0b011:
      pathchanger(false);
      break;
    case 0b010:
      moveServos(45);
      break;
    case 0b001:
      moveServos(-45);
      break;
  }
}


void stopRotor() {
  digitalWrite(ROTOR_PIN1, LOW);
  digitalWrite(ROTOR_PIN2, LOW);
}

void stoppathchanger() {
  digitalWrite(P_CHANGER_PIN1, LOW);
  digitalWrite(P_CHANGER_PIN2, LOW);
}

void rotateRotor(bool direction) {
  digitalWrite(ROTOR_PIN1, direction ? HIGH : LOW);
  digitalWrite(ROTOR_PIN2, direction ? LOW : HIGH);
}

void pathchanger(bool direction) {
  // Read limit switches first
  int pcfwlimit = digitalRead(PC_FW_LIMIT);
  int pcbwlimit = digitalRead(PC_BW_LIMIT);

  // Prevent movement if limit is reached
  if ((direction && pcbwlimit == HIGH) || (!direction && pcfwlimit == HIGH)) {
    // Stop motor
    digitalWrite(P_CHANGER_PIN1, LOW);
    digitalWrite(P_CHANGER_PIN2, LOW);
    return;  // Exit without moving
  }

  stopRotor();
  digitalWrite(P_CHANGER_PIN1, direction ? HIGH : LOW);
  digitalWrite(P_CHANGER_PIN2, direction ? LOW : HIGH);
}

void moveServos(int angle) {  
  servo1.write(90 + angle);
  servo2.write(90 - angle);
}
