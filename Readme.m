# 🔒 ROS 2 기반 홈 시큐리티 자율순찰 및 AI 화재 경보 로봇

스마트폰 카메라의 객체 인식 AI와 터틀봇3(TurtleBot3 Burger)의 Navigation2 시스템을 융합한 **자율 순찰 및 웹 관제 홈 시큐리티 로봇** 시스템입니다. 자율 주행 중 화재(또는 이상 징후)를 포착하면 실시간으로 비상 정지하고 관제 센터에 사이렌 경보를 울립니다.

---

## 🛠️ 개발 환경 및 하드웨어 사양
* **로봇 플랫폼:** TurtleBot3 Burger (SBC: Raspberry Pi 4, OpenCR)
* **운영체제 및 ROS 버전:** Ubuntu 22.04 LTS / ROS 2 Humble
* **센서:** LDS-01 LiDAR, 스마트폰 독립 카메라 (Edge AI 연산)
* **관제 인터페이스:** HTML5, ROSLIB.js, Web Audio API 사운드 엔진

---

## ⚠️ 타 환경(새 터틀봇/새 노트북)에서 실행 시 최초 1회 필수 세팅

본 프로젝트 코드를 처음 다운로드받아 다른 터틀봇 및 노트북 환경에서 구동하려는 경우, 스크립트 실행 전에 아래 3가지 사전 작업이 완료되어야 합니다.

### 1) 와이파이(Network) 및 IP 주소 동기화
노트북과 터틀봇이 **같은 와이파이 공유기**에 연결되어 있어야 통신이 가능합니다.
1. 본인이 사용할 터틀봇의 IP 주소를 확인합니다.
2. 다운받은 프로젝트 폴더 내의 `run_all.sh` 파일을 메모장으로 열어 상단의 IP 변수를 본인 환경에 맞게 수정합니다.
   ```bash
   # run_all.sh 파일을 열어 수정
   TURTLEBOT_IP="본인의_터틀봇_IP" 

    노트북 터미널의 ~/.bashrc 파일 맨 밑에 적힌 ROS_DOMAIN_ID가 터틀봇의 ID와 일치하는지 확인합니다.

2) 터틀봇 본체(SBC)에 보안 패키지 복사 및 빌드

자율순찰 제어 코드(home_security_pkg)는 터틀봇 본체 컴퓨터 안에서 실행되어야 하므로, 로봇 내부로 코드를 전송하고 빌드해야 합니다.

    노트북 터미널을 열고, 프로젝트 폴더 안에서 아래 명령어를 쳐서 패키지를 터틀봇으로 원격 전송합니다.
    Bash

    scp -r home_security_pkg ubuntu@본인_터틀봇_IP:~/turtlebot3_ws/src/

    터틀봇에 SSH로 접속하여 패키지를 빌드(컴파일)해 줍니다.
    Bash

    ssh ubuntu@본인_터틀봇_IP
    cd ~/turtlebot3_ws
    colcon build --packages-select home_security_pkg
    source install/setup.bash
    exit

3) 지도 파일 배치

본인이 맵핑한 지도 파일(my_50_room_map.yaml 및 my_50_room_map.pgm)을 노트북 PC의 홈 디렉토리(~/) 바로 밑에 넣어두어야 내비게이션(Nav2)이 지도를 정상적으로 인식합니다.
🚀 원터치 초고속 실행 방법 (Quick Start)

사전 세팅이 완료되었다면, 일일이 터미널을 4개 띄우고 SSH 접속할 필요 없이 통합 스크립트 하나로 전체 시스템을 한 방에 기동할 수 있습니다.
1) 필수 프로그램 설치 (노트북 PC 담당)

백그라운드 제어권 분할을 위해 노트북 PC 터미널에 tmux를 먼저 설치합니다.
Bash

sudo apt update && sudo apt install tmux -y

2) 레포지토리 클론 및 실행 권한 부여
Bash

git clone [https://github.com/YOUR_GITHUB_ID/my-turtlebot-security.git](https://github.com/YOUR_GITHUB_ID/my-turtlebot-security.git)
cd my-turtlebot-security
chmod +x run_all.sh

3) 올인원 시스템 원터치 런칭
Bash

./run_all.sh

    스크립트 실행 중 터틀봇 SSH 비밀번호(기본: ubuntu)를 요구하면 입력해 줍니다.

    실행 즉시 백그라운드에서 SBC Bringup, Rosbridge, Nav2, Patrol Node가 순서대로 자동 동기화됩니다.

4) 관제 대시보드 연결

    노트북에서 프로젝트 폴더 내의 dashboard.html 파일을 크롬 브라우저로 실행합니다.

    ⭐ 중요: 브라우저 보안 정책상 사운드 차단을 해제하기 위해, 화면의 빈 공간을 마우스로 꼭 한 번 딸깍 클릭해 줍니다.

    실시간 카메라 피드, 라이다 레이더 레이아웃, 보안 로그가 정상 수신되는지 확인합니다.

🎬 주요 시연 시나리오 및 핵심 기능
1. 🔄 자율 초기 위치 정렬 (INIT_ROTATION)

    노드가 구동되자마자 스스로 reinitialize_global_localization 서비스를 호출하여 AMCL 파티클을 맵 전체에 분산시킵니다.

    이후 로봇이 제자리에서 2바퀴(약 12초) 자율 회전하며 라이다 데이터를 매칭해 정확한 자기 위치를 스스로 특정합니다.

2. 🗺️ 정밀 웨이포인트 자율 순찰 (PATROL)

    맵 매칭이 끝나면 사전에 최적화된 4개의 구석 구역 절대 좌표(waypoints)를 기반으로 완벽한 글로벌 및 로컬 경로 계획을 수립하여 순찰을 시작합니다.

    이동 경로 중 마주치는 동적 장애물(사람의 발, 의자 등)은 내장된 고성능 레이더 회피 알고리즘을 통해 자율적으로 우회 주행합니다.

3. 🚨 스마트폰 AI 화재 감지 및 실시간 비상 정지 (EMERGENCY)

    로봇 정면에 장착된 스마트폰 카메라가 화재(fire) 요인을 인식하여 ROS 토픽을 발행하면, 순찰 노드가 이를 인터럽트하여 0.1초 만에 모터 속도를 0으로 묶어 비상 정지시킵니다.

    동시에 중앙 관제 대시보드의 전광판이 적색(🔥 FIRE DETECTED)으로 반전되며, 웹 오디오 합성 엔진을 통해 노트북 스피커에서 고주파 비상 사이렌 경보음이 울리고, 타임스탬프 기반 보안 로그 기록이 강제 박제됩니다.

    위험 요소를 치워 상태가 safe로 복귀하면, 가던 순찰 경로를 다시 인계받아 마저 이동합니다.

4. ⌨️ 하이브리드 제어권 인계 (MANUAL)

    비상 상황 시 관제자가 대시보드에서 ⚠️ 원격 수동 제어 강제 전환 버튼을 누르면 자율 주행 모드가 칼같이 중단되며, 화면 마우스 조이스틱 혹은 키보드(W, A, S, D)를 통해 로봇을 실시간으로 수동 첩보 조종할 수 있습니다.

🛑 시스템 안전 종료 방법

시연이 끝난 후 백그라운드에서 돌고 있는 모든 로봇 프로세스를 한 방에 클린 종료하려면 노트북 터미널에 아래 명령을 입력합니다.
Bash

tmux kill-session -t security
