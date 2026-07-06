#!/usr/bin/env python3
"""patrol_node: 자율 순찰 ↔ 수동 조종 ↔ 경보 상태머신 (QoS 보정 완료 버전)"""
import json
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan 
from rclpy.qos import QoSProfile, ReliabilityPolicy # 💡 QoS 에러 해결을 위한 임포트

# 순찰 경로 데이터 (실측 스케줄러)
PATROL_ROUTE = [(0.10, 0.0, 4.0), (0.0, 0.5, 3.1),
                (0.10, 0.0, 4.0), (0.0, 0.5, 3.1)]
MANUAL_TIMEOUT = 0.5 #

class PatrolNode(Node):
    def __init__(self):
        super().__init__('patrol_node')
        
        # 1. 웹 대시보드 및 AI 통신용 구독자 등록
        self.sub_mode = self.create_subscription(String, '/mode', self.on_mode, 10)
        self.sub_manual = self.create_subscription(String, '/manual_cmd', self.on_manual, 10)
        self.sub_det = self.create_subscription(Bool, '/detection', self.on_detect, 10)
        
        # 💡 2. 라이다(터틀봇3 기본 /scan) QoS 매칭 구독 설정
        lidar_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT  # 터틀봇 센서 노드와 호환성 매칭
        )
        self.sub_scan = self.create_subscription(LaserScan, '/scan', self.on_scan, lidar_qos) #
        
        # 3. 퍼블리셔 등록
        self.pub_vel = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pub_event = self.create_publisher(String, '/event', 10)
        self.pub_state = self.create_publisher(String, '/patrol_state', 10)
        self.pub_alert = self.create_publisher(Bool, '/alert', 10) # 알려진 한계 ① 해결용
        
        # 4. 제어 변수 초기화
        self.state = 'PATROL'  # PATROL / MANUAL / ALERT 기본 상태 설정
        self.route = []
        self.manual = {'lx': 0.0, 'az': 0.0}
        self.last_manual = 0.0
        self.is_emergency = False  # 라이다 긴급 브레이크 플래그
        
        # 5. 주기적 제어 타이머 (10Hz)
        self.timer = self.create_timer(0.1, self.tick)
        self.get_logger().info('patrol_node 시작 (PATROL) - 안전장치 및 QoS 매칭 완료')

    def set_state(self, s):
        if s != self.state:
            self.state = s
            
            # 대시보드 상태 뱃지 업데이트 엣지 발행
            msg = String()
            msg.data = s
            self.pub_state.publish(msg)   
            
            # ALERT 진입 시 LED/부저 노드용 경보 토픽 연동
            alert_msg = Bool()
            if s == 'ALERT':
                alert_msg.data = True
                self.pub_alert.publish(alert_msg)
                self.get_logger().warn('🚨 ALERT 상태 진입! 경보 발행.')
            else:
                alert_msg.data = False
                self.pub_alert.publish(alert_msg)

    def on_mode(self, msg):
        if msg.data in ('patrol', 'manual'):
            self.set_state('PATROL' if msg.data == 'patrol' else 'MANUAL')
            self.route = []

    def on_manual(self, msg):
        try:
            self.manual = json.loads(msg.data)
            self.last_manual = time.time()
        except json.JSONDecodeError:
            pass

    def on_detect(self, msg):
        if msg.data and self.state == 'PATROL':
            self.set_state('ALERT')  # 정지 + 이벤트 타임라인 기록 유도
            ev = String()
            ev.data = json.dumps({'type': 'intruder', 'ts': time.time()})
            self.pub_event.publish(ev)

    def on_scan(self, msg):
        # 터틀봇 기준 전방 시야각(정면 기준 좌우 약 15도 범위) 추출
        front_ranges = msg.ranges[0:15] + msg.ranges[345:360]
        valid_ranges = [r for r in front_ranges if r > 0.02]  # 노이즈 및 오차값 필터링
        
        if valid_ranges:
            min_dist = min(valid_ranges)
            # 전방 0.3m (30cm) 이내 충돌 위험물 감지 시 브레이크 활성화
            if min_dist < 0.3:
                if not self.is_emergency:
                    self.get_logger().error(f'⚠️ 긴급 브레이크! 전방 장애물 감지: {min_dist:.2f}m')
                self.is_emergency = True
            else:
                self.is_emergency = False

    def tick(self):
        cmd = Twist()
        
        # [최우선 안전장치] 긴급 정지 상태 시 강제로 속도 0 발행 (M7)
        if self.is_emergency:
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0
            self.pub_vel.publish(cmd)
            return

        # 상태별 모드 중재 스케줄러
        if self.state == 'PATROL':
            if not self.route:
                self.route = [list(s) for s in PATROL_ROUTE]  # 경로 무한 반복
            lx, az, remain = self.route[0]
            cmd.linear.x, cmd.angular.z = float(lx), float(az)
            self.route[0][2] = remain - 0.1
            if self.route[0][2] <= 0:
                self.route.pop(0)
                
        elif self.state == 'MANUAL':
            # 수동 입력 소실 타임아웃 예외 처리 (S2)
            if (time.time() - self.last_manual) < MANUAL_TIMEOUT:
                cmd.linear.x = float(self.manual.get('lx', 0.0))
                cmd.angular.z = float(self.manual.get('az', 0.0))
                
        # ALERT 상태일 때는 자동으로 속도가 (0, 0)인 기본 cmd 객체가 발행됩니다.
        self.pub_vel.publish(cmd)

def main():
    rclpy.init()
    node = PatrolNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
