# INTERFACE.md

# 홈 시큐리티 순찰 로봇 토픽 인터페이스 정의서

## 1. 문서 개요

본 문서는 홈 시큐리티 순찰 로봇 프로젝트에서 사용하는 ROS2 토픽 인터페이스를 정의한다.
AI 감지 모듈, ROS2 노드, 웹 대시보드 및 TurtleBot3 Burger 간의 데이터 송수신 규칙을 통일하여 안정적인 시스템 통합을 목표로 한다.

---

# 2. 전체 토픽 명세

| 토픽명 | 메시지 타입 | Publisher | Subscriber | 주기 | 성격 | QoS | 설명 |
|--------|----------------------------|-----------------|-----------------|-----------|-----------|-------------|--------------------------------|
| /scan | sensor_msgs/msg/LaserScan | TurtleBot3 LiDAR | patrol_node | 약 5Hz | 연속 | BEST_EFFORT | 전방 장애물 거리 정보 |
| /detection | std_msgs/msg/Bool | AI 감지 모듈 | patrol_node | 감지 시 | 엣지 | RELIABLE | 사람 감지 여부 |
| /mode | std_msgs/msg/String | 웹 대시보드 | patrol_node | 변경 시 | 엣지 | RELIABLE | PATROL / MANUAL 모드 변경 |
| /manual_cmd | std_msgs/msg/String | 웹 대시보드 | patrol_node | 10Hz | 연속 | RELIABLE | 수동 조종 명령(JSON) |
| /cmd_vel | geometry_msgs/msg/Twist | patrol_node | TurtleBot3 Burger | 10Hz | 연속 | RELIABLE | 로봇 속도 제어 |
| /event | std_msgs/msg/String | patrol_node | 웹 대시보드 | 이벤트 발생 시 | 엣지 | RELIABLE | 침입 이벤트 정보(JSON) |
| /patrol_state | std_msgs/msg/String | patrol_node | 웹 대시보드 | 상태 변경 시 | 엣지 | RELIABLE | 현재 상태(PATROL / MANUAL / ALERT) |
| /alert | std_msgs/msg/Bool | patrol_node | LED / Buzzer | ALERT 진입 시 | 엣지 | RELIABLE | 경보 신호 |

---

# 3. 토픽 데이터 흐름

| Publisher | Topic | Subscriber | 목적 |
|-----------|-------|------------|---------------------------|
| AI 감지 모듈 | /detection | patrol_node | 사람 감지 이벤트 전달 |
| TurtleBot3 LiDAR | /scan | patrol_node | 장애물 거리 측정 |
| 웹 대시보드 | /mode | patrol_node | 순찰/수동 모드 변경 |
| 웹 대시보드 | /manual_cmd | patrol_node | 수동 조종 |
| patrol_node | /cmd_vel | TurtleBot3 Burger | 이동 제어 |
| patrol_node | /event | 웹 대시보드 | 이벤트 기록 |
| patrol_node | /patrol_state | 웹 대시보드 | 현재 상태 표시 |
| patrol_node | /alert | LED / Buzzer | 경보 발생 |

---

# 4. 인터페이스 규칙

- `/scan`은 TurtleBot3 LiDAR에서 연속 발행한다.
- `/cmd_vel`과 `/manual_cmd`는 10Hz 주기로 발행한다.
- `/detection`은 사람을 감지한 순간 1회 발행한다.
- `/event`는 침입 이벤트 발생 시 JSON 형식으로 발행한다.
- `/patrol_state`는 상태 변경 시에만 발행한다.
- `/alert`는 ALERT 상태 진입 시 1회 발행한다.
- 제어 토픽은 RELIABLE QoS를 사용한다.
- LiDAR(`/scan`)는 TurtleBot3 기본 설정에 따라 BEST_EFFORT QoS를 사용한다.

---

# 5. 상태별 토픽 사용

| 상태 | 사용 토픽 |
|------|------------------------------|
| PATROL | /scan, /cmd_vel, /patrol_state |
| ALERT | /event, /alert, /patrol_state |
| MANUAL | /manual_cmd, /cmd_vel, /patrol_state |

---

# 6. 시스템 통신 구조

```text
AI 감지 모듈
      │
      ├── /detection
      ▼
 patrol_node
      │
      ├── /cmd_vel ─────▶ TurtleBot3 Burger
      ├── /event ───────▶ 웹 대시보드
      ├── /patrol_state ▶ 웹 대시보드
      └── /alert ───────▶ LED / Buzzer

LiDAR(/scan)
      │
      ▼
 patrol_node

웹 대시보드
      │
      ├── /mode
      └── /manual_cmd
```

---

# 7. 비고

- ROS2 Humble 기반으로 구현하였다.
- TurtleBot3 Burger의 LiDAR(`/scan`)를 이용하여 장애물을 감지한다.
- 사람 감지는 스마트폰 AI 모듈을 이용하여 수행한다.
- 웹 대시보드는 rosbridge(WebSocket)를 통해 ROS2와 통신한다.
- 본 인터페이스 정의서는 GitHub 저장소의 실제 구현을 기준으로 작성하였다.
