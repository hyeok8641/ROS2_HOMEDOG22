#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String
from geometry_msgs.msg import Twist
from nav2_msgs.action import NavigateToPose
from std_srvs.srv import Empty  # 💡 글로벌 로컬라이제이션 재초기화 서비스 메시지 타입
import json
import random

class PatrolNode(Node):
    def __init__(self):
        super().__init__('patrol_node')
        
        # 1. 서브스크라이버 및 퍼블리셔 선언
        self.mode_sub = self.create_subscription(String, '/mode', self.mode_callback, 10)
        self.manual_sub = self.create_subscription(String, '/manual_cmd', self.manual_callback, 10)
        
        # 💡 [신규 추가] 스마트폰 AI 화재 감지 데이터를 받기 위한 서브스크라이버 선언
        self.det_sub = self.create_subscription(String, '/detection_msg', self.detection_callback, 10)
        
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.state_pub = self.create_publisher(String, '/patrol_state', 10)
        
        # 2. Nav2 주행을 위한 Action Client 선언
        self.nav_to_pose_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # 💡 3. 글로벌 위치 초기화 서비스 클라이언트 선언
        self.global_loc_client = self.create_client(Empty, '/reinitialize_global_localization')
        
        # 4. 상태 제어 변수
        self.current_mode = 'INIT_ROTATION' # 💡 시작 모드: 제자리 회전 위치 파악 모드로 출발!
        self.latest_manual_twist = Twist()
        
        # 💡 [신규 추가] 화재 상황을 추적하기 위한 보안 관리 상태 변수들
        self.is_emergency = False
        self.prev_mode = 'INIT_ROTATION'
        
        # 5. 실습실 환경에 맞는 자율 순찰 웨이포인트(X, Y) 설정
        self.waypoints = [
            {'x': 0.7, 'y': -7.6},
            {'x': -4.2, 'y': 3.4},
            {'x': -7.7, 'y': -4.5},
            {'x': 2.7, 'y': -0.3}
        ]
        self.current_wp_idx = 0
        self.nav_goal_handle = None
        self.is_moving_to_wp = False
        
        # 💡 자동 2바퀴 회전 제어용 카운터 (0.1초마다 가동되므로 120 카운트 = 약 12초 회전)
        self.rotation_counter = 0

        # 상태 송신 및 주행 제어용 10Hz 메인 타이머 루프
        self.timer = self.create_timer(0.1, self.main_control_loop)
        
        self.get_logger().info("🔒 [자동 위치 매칭] 360도 자율 회전 정렬 노드가 기동되었습니다.")
        
        # 💡 노드가 켜지자마자 서비스 가동 트리거
        self.trigger_global_localization()

    # 💡 [신규] 글로벌 로컬라이제이션 서비스 호출 함수
    def trigger_global_localization(self):
        while not self.global_loc_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('AMCL 서비스를 대기하는 중...')
            
        req = Empty.Request()
        self.get_logger().info('🎯 [위치 자동 파악] 글로벌 로컬라이제이션 재초기화 호출! 파티클 분산 시작.')
        self.global_loc_client.call_async(req)

    # 💡 [신규 추가] 스마트폰 카메라의 화재 정보를 분석하여 강제 브레이크를 거는 제어 엔진
    def detection_callback(self, msg):
        try:
            data = json.loads(msg.data)
            target = data.get('target')
            
            # 자율순찰(PATROL) 모드이거나 위치파악 회전(INIT_ROTATION) 중일 때 화재 감지 시 정지
            if target == 'fire':
                if not self.is_emergency:
                    self.get_logger().warn('🔥 [화재 경보] 자율 주행 경로를 전면 취소하고 제자리에 즉각 비상 정지합니다!')
                    self.is_emergency = True
                    self.prev_mode = self.current_mode  # 화재 발생 직전 로봇 상태 백업
                    self.current_mode = 'EMERGENCY'
                    self.cancel_nav_goal()  # Nav2가 움직이던 목표지점 주행 취소
            else:
                # 화재 위험이 해제되어 'safe'가 들어오면 원래 수행하던 모드로 복귀
                if self.is_emergency and target == 'safe':
                    self.get_logger().info('🟢 [상황 해제] 화재 위험 요소가 사라져 순찰 시스템을 재개합니다.')
                    self.is_emergency = False
                    self.current_mode = self.prev_mode  # 백업해뒀던 이전 상태로 원상복구
        except Exception as e:
            pass

    def mode_callback(self, msg):
        # 대시보드 텍스트가 대소문자 섞여 들어올 때를 대비해 처리
        new_mode = msg.data.upper()
        if new_mode in ['PATROL', 'MANUAL']:
            # 현재 강제 회전 모드이거나 화재 비상 정지 상황이 아닐 때만 전환 허용
            if self.current_mode != 'INIT_ROTATION' and not self.is_emergency:
                self.current_mode = new_mode
                self.get_logger().info(f"🔄 모드 전환 승인: {self.current_mode}")
                
                if self.current_mode == 'MANUAL':
                    self.cancel_nav_goal()
                    stop_twist = Twist()
                    self.cmd_vel_pub.publish(stop_twist)
                    self.latest_manual_twist = stop_twist
                else:
                    self.current_wp_idx = 0
                    self.is_moving_to_wp = False

    def manual_callback(self, msg):
        # 💡 대시보드 문자열 패킷 디코딩 및 수동 속도 주입 완벽 보정
        if self.current_mode == 'MANUAL' and not self.is_emergency:
            try:
                cmd_data = json.loads(msg.data)
                twist = Twist()
                twist.linear.x = float(cmd_data.get('lx', 0.0))
                twist.angular.z = float(cmd_data.get('az', 0.0))
                self.latest_manual_twist = twist
            except Exception as e:
                # 대시보드에서 보낸 패킷 백업 예외 처리
                pass

    def send_nav_goal(self, x, y):
        if not self.nav_to_pose_client.wait_for_server(timeout_sec=2.0):
            self.get_logger().error("❌ Nav2 Action Server를 찾을 수 없습니다!")
            return

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.orientation.w = 1.0
        
        self.get_logger().info(f"🗺️ Nav2 순찰 목표 전송: WP[{self.current_wp_idx}] -> (X: {x}, Y: {y})")
        self.is_moving_to_wp = True
        
        send_goal_future = self.nav_to_pose_client.send_goal_async(goal_msg)
        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.is_moving_to_wp = False
            return
        self.nav_goal_handle = goal_handle
        get_result_future = goal_handle.get_result_async()
        get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        status = future.result().status
        if status == 4: # SUCCEEDED
            self.get_logger().info(f"✅ WP[{self.current_wp_idx}] 지점 도착 완료!")
            self.current_wp_idx = (self.current_wp_idx + 1) % len(self.waypoints)
        self.is_moving_to_wp = False

    def cancel_nav_goal(self):
        if self.nav_goal_handle is not None:
            self.nav_goal_handle.cancel_goal_async()
            self.nav_goal_handle = None
        self.is_moving_to_wp = False

    # 10Hz 메인 제어 루프
    def main_control_loop(self):
        state_msg = String()
        state_msg.data = self.current_mode
        self.state_pub.publish(state_msg)
        
        # 💡 [신규 추가 - 최우선 순위 인터럽트 브레이크]
        # 화재가 감지되어 EMERGENCY가 되면 밑의 주행 로직을 전부 무시하고 0.1초마다 모터에 0을 강제로 주입합니다.
        if self.current_mode == 'EMERGENCY' or self.is_emergency:
            stop_twist = Twist()
            stop_twist.linear.x = 0.0
            stop_twist.angular.z = 0.0
            self.cmd_vel_pub.publish(stop_twist)
            return
        
        # 💡 [최종 진화 시나리오]: 켜지자마자 제자리 돌며 위치 동기화 가동
        if self.current_mode == 'INIT_ROTATION':
            twist = Twist()
            twist.linear.x = 0.0
            twist.angular.z = 0.5  # 제자리 회전 속도 (초당 약 30도 회전)
            self.cmd_vel_pub.publish(twist)
            
            self.rotation_counter += 1
            # 12초(120 카운트) 동안 회전하면 대략 2바퀴를 돌며 AMCL 파티클이 수렴합니다.
            if self.rotation_counter >= 120:
                self.get_logger().info("✅ [위치 자동 파악] 2바퀴 자율 회전 완료! 위치가 특정되었습니다. 순찰 모드 진입!")
                # 정지 패킷 한 번 방출
                stop_twist = Twist()
                self.cmd_vel_pub.publish(stop_twist)
                
                # 자동으로 자율 순찰(PATROL) 모드로 변경!
                self.current_mode = 'PATROL'
        
        # 수동 제어 모드일 때 (조이스틱/키보드 전달 통로 100% 개방)
        elif self.current_mode == 'MANUAL':
            self.cmd_vel_pub.publish(self.latest_manual_twist)
            
        # 자율 순찰 모드일 때
        elif self.current_mode == 'PATROL':
            if not self.is_moving_to_wp:
                target_wp = self.waypoints[self.current_wp_idx]
                self.send_nav_goal(target_wp['x'], target_wp['y'])

def main(args=None):
    rclpy.init(args=args)
    node = PatrolNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        final_stop = Twist()
        node.cmd_vel_pub.publish(final_stop)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
