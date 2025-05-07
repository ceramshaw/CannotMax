import json
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import math
from simulator.battle_field import Battlefield
from constants import UNIT_CONFIG
from combat_calculator import calculate_damage
from simulator.monsters import AttackState, Monster, MonsterFactory
from simulator.simulate import MONSTER_MAPPING
from simulator.utils import REVERSE_MONSTER_MAPPING, Faction
from simulator.vector2d import FastVector
from unit import Unit

class SandboxSimulator:
    def __init__(self, master : tk.Tk, battle_data):
        self.master = tk.Toplevel(master)
        master.title("沙盒模拟器")
        self.num_monsters = 58
        self.load_assets()
        self.battle_data = battle_data
        self.init_game()
        self.create_widgets()
        self.speed_multiplier = 1.0

    def load_assets(self):
        self.icons = {}
        with open("simulator/monsters.json", encoding='utf-8') as f:
            self.monster_data = json.load(f)["monsters"]
    
        for unit_id in range(self.num_monsters):
            try:
                image = Image.open(f'images/{unit_id + 1}.png')
                self.icons[unit_id] = {
                    "red": ImageTk.PhotoImage(image.resize((40, 40))),
                    "blue": ImageTk.PhotoImage(image.resize((40, 40)).transpose(Image.FLIP_LEFT_RIGHT))
                }
            except Exception as e:
                print(f"Error loading icon: {e}")

    def init_game(self):
        self.grid_width = 13
        self.grid_height = 9
        self.cell_size = 90
        self.canvas_width = self.grid_width * self.cell_size
        self.canvas_height = self.grid_height * self.cell_size
        self.units = []
        self.selected_team = None
        self.selected_unit_id = None
        self.simulating = False
        self.simulation_id = None

        self.battle_field = Battlefield(self.monster_data)
        self.setup_battle_field()
        

    def setup_battle_field(self):
        scene_config = self.battle_data
        # scene_config = {"left": {"宿主流浪者": 7, "污染躯壳": 14, "凋零萨卡兹": 5}, "right": {"大喷蛛": 4, "杰斯顿": 1, "衣架": 10}, "result": "right"}

        # 用户配置
        left_army = scene_config["left"]
        right_army = scene_config["right"]

        if self.battle_field.setup_battle(left_army, right_army, self.monster_data):
            return True

    def create_widgets(self):
        control_frame = tk.Frame(self.master)
        control_frame.pack(pady=5)

        # 队伍控制面板
        self.create_team_controls(control_frame)

        # 新增速度控制组件
        speed_frame = tk.Frame(control_frame)
        speed_frame.pack(side=tk.LEFT, padx=10)

        tk.Label(speed_frame, text="倍速:").pack(side=tk.LEFT)
        self.speed_entry = tk.Entry(speed_frame, width=5)
        self.speed_entry.pack(side=tk.LEFT)
        self.speed_entry.insert(0, "1.0")

        tk.Button(speed_frame, text="应用", command=self.apply_speed).pack(side=tk.LEFT)

        # 功能按钮
        tk.Button(control_frame, text="开始模拟", command=self.start_simulation).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="清空", command=self.clear_sandbox).pack(side=tk.LEFT, padx=5)
        self.timer_label = tk.Label(control_frame, text="0.00秒")
        self.timer_label.pack(side=tk.RIGHT, padx=100)

        # 沙盒画布
        self.canvas = tk.Canvas(self.master,
                                width=self.canvas_width,
                                height=self.canvas_height,
                                bg='white')
        self.canvas.pack(pady=10)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.draw_grid()


    def apply_speed(self):
        try:
            new_speed = float(self.speed_entry.get())
            if new_speed <= 0:
                raise ValueError("速度必须大于0")

            self.speed_multiplier = new_speed
            # 如果正在运行则重新启动模拟
            if self.simulating:
                self.master.after_cancel(self.simulation_id)
                self.simulate()
        except ValueError as e:
            messagebox.showerror("错误", f"无效的速度值: {e}")
            self.speed_entry.delete(0, tk.END)
            self.speed_entry.insert(0, str(self.speed_multiplier))

    def create_team_controls(self, parent):
        teams_frame = tk.Frame(parent)
        teams_frame.pack(side=tk.LEFT)

        self.create_team_panel(teams_frame, "red", "红")
        self.create_team_panel(teams_frame, "blue", "蓝")

    def create_team_panel(self, parent, team, name):
        frame = tk.Frame(parent)
        frame.pack(side=tk.LEFT, padx=10)

        tk.Label(frame, text=name).pack()

        # 对整数id进行排序
        unit_ids = range(1, 56)

        for unit_id in unit_ids:
            if unit_id % 10 == 1:
                row_frame = tk.Frame(frame)
                row_frame.pack()
            btn = tk.Button(row_frame,
                            image=self.icons[unit_id][team],
                            command=lambda t=team, u=unit_id: self.select_unit(t, u))
            btn.image = self.icons[unit_id][team]
            btn.pack(side=tk.LEFT, padx=2, pady=2)

    def select_unit(self, team, unit_id):
        self.selected_team = team
        self.selected_unit_id = unit_id

    def draw_grid(self):
        for i in range(self.grid_width + 1):
            x = i * self.cell_size
            self.canvas.create_line(x, 0, x, self.canvas_height, fill='gray')
        for i in range(self.grid_height + 1):
            y = i * self.cell_size
            self.canvas.create_line(0, y, self.canvas_width, y, fill='gray')

    def on_canvas_click(self, event):
        # 修改判断条件
        if not self.selected_team or not self.selected_unit_id:
            return

        # 转换坐标
        x = event.x / self.cell_size
        y = event.y / self.cell_size

        # 检查放置区域
        if (self.selected_team == 'red' and x >= 6.5) or \
                (self.selected_team == 'blue' and x < 6.5):
            return

        # 碰撞检测
        for unit in self.units:
            if math.hypot(unit.x - x, unit.y - y) < 0.2:
                return

        # 创建新单位（使用unit_id）
        new_unit = Unit(self.selected_team, self.selected_unit_id, x, y)
        data = next((m for m in self.monster_data if m["名字"] == MONSTER_MAPPING[self.selected_unit_id]), None)
        monster = MonsterFactory.create_monster(data, Faction.RIGHT if self.selected_team == 'blue' else Faction.LEFT, FastVector(x, y), self.battle_field)
        self.battle_field.append_monster(monster
        )
        self.units.append(new_unit)
        self.draw_unit(new_unit, monster)

    def draw_unit(self, unit, monster):
        x = unit.x * self.cell_size
        y = unit.y * self.cell_size

        # 绘制单位图标
        image = self.icons[unit.unit_id][unit.team]
        self.canvas.create_image(x, y, image=image, tags=("unit",))

        # 生命条参数
        bar_width = 40  # 与图标同宽
        bar_height = 5
        max_health = unit.max_health
        current_health = unit.health

        # 计算生命条位置（图标下方）
        bar_y = y + 25  # 图标中心Y坐标 + 图标半径

        # 绘制生命条背景（深红色）
        self.canvas.create_rectangle(
            x - bar_width / 2, bar_y - bar_height / 2,
            x + bar_width / 2, bar_y + bar_height / 2,
            fill="#400000", outline="" #"gray"
        )


        # 计算当前生命值比例
        health_ratio = min(1, current_health / max_health)
        current_width = max(1, bar_width * health_ratio)  # 保持最小1像素可见

        # 绘制当前生命条（红色）
        self.canvas.create_rectangle(
            x - bar_width / 2, bar_y - bar_height / 2,
            x - bar_width / 2 + current_width, bar_y + bar_height / 2,
            fill="#FF3030", outline=""  #"yellow"
        )

        # 技力条（在生命条下方）
        burn_bar_y = bar_y + 7  # 生命条下方7像素
        burn_bar_width = 40

        # 当前损伤值比例
        skill_ratio = min(1, unit.skill / unit.max_skill)
        current_width = burn_bar_width * skill_ratio

        # 背景（黑色）
        self.canvas.create_rectangle(
            x - burn_bar_width / 2, burn_bar_y - 3,
            x + burn_bar_width / 2, burn_bar_y + 3,
            fill="black", outline=""
        )

        color = "#FF3030"
        if monster.attack_state == AttackState.后摇:
            color = "#30FF30"
        elif monster.attack_state == AttackState.等待:
            color = "yellow"
        # 当前进度（黄色）
        self.canvas.create_rectangle(
            x - burn_bar_width / 2, burn_bar_y - 3,
            x - burn_bar_width / 2 + current_width, burn_bar_y + 3,
            fill=color, outline=""
        )

        # # 冷却状态显示灰色
        # if unit.burn_cooldown > 0:
        #     self.canvas.create_rectangle(
        #         x - burn_bar_width / 2, burn_bar_y - 3,
        #         x + burn_bar_width / 2, burn_bar_y + 3,
        #         fill="gray", outline=""
        #     )
        # else:
        #     # 当前损伤值比例
        #     burn_ratio = (1000 - unit.burn_damage) / 1000
        #     current_width = burn_bar_width * burn_ratio

        #     # 背景（黑色）
        #     self.canvas.create_rectangle(
        #         x - burn_bar_width / 2, burn_bar_y - 3,
        #         x + burn_bar_width / 2, burn_bar_y + 3,
        #         fill="black", outline=""
        #     )
        #     # 当前进度（黄色）
        #     self.canvas.create_rectangle(
        #         x - burn_bar_width / 2, burn_bar_y - 3,
        #         x - burn_bar_width / 2 + current_width, burn_bar_y + 3,
        #         fill="yellow", outline=""
        #     )

    def start_simulation(self):
        if not self.simulating:
            self.simulating = True
            self.battle_field.setup_battle({}, {}, self.monster_data)
            self.simulate()

    def simulate(self):
        if not self.simulating:
            return
        
        result = self.battle_field.run_one_frame()

        if result:
            if result == Faction.LEFT:
                self.show_result("左方胜利！")
            else:
                self.show_result("右方胜利！")

        interval = max(1, int(33 / self.speed_multiplier))  # 保持最小1ms间隔
        self.simulation_id = self.master.after(interval, self.simulate)

        # 重绘画布
        self.canvas.delete("all")
        self.draw_grid()


        if len(self.battle_field.alive_monsters) > len(self.units):
            for i in range(len(self.units), len(self.battle_field.alive_monsters)):
                new_unit = Unit('red', 0, 0, 0)
                self.units.append(new_unit)

        index = 0
        for monster in self.battle_field.alive_monsters:
            unit = self.units[index]
            index += 1
            if monster.is_alive:
                unit.unit_id = REVERSE_MONSTER_MAPPING[monster.name]
                unit.team = 'red' if monster.faction == Faction.LEFT else 'blue'
                unit.health = monster.health
                unit.max_health = monster.max_health
                unit.x = monster.position.x
                unit.y = monster.position.y
                unit.skill = monster.get_skill_bar()
                unit.max_skill = monster.get_max_skill_bar()
                self.draw_unit(unit, monster)

        for monster in self.battle_field.alive_monsters:
            if monster.is_alive and monster.target is not None:
                self.canvas.create_line(
                    monster.position.x * self.cell_size, monster.position.y * self.cell_size,
                    monster.target.position.x * self.cell_size, monster.target.position.y * self.cell_size,
                    fill="#FF3030" if monster.faction == Faction.LEFT else "#3030FF", width=1, arrow='last')
        self.timer_label.config(text=f"{self.battle_field.gameTime:.2f}秒")

        # dead_units = []
        # for unit in self.units:

        #     # 修改后的攻击目标选择逻辑
        #     effects = unit.config.get("effect", "").split()
        #     enemies = [u for u in self.units if u.team != unit.team and u.is_alive]

        #     # 根据效果决定攻击目标数量
        #     if "打2" in effects:
        #         # 找到最近的两位敌人
        #         sorted_enemies = sorted(enemies, key=lambda e: self.calculate_distance(unit, e))
        #         main_targets = sorted_enemies[:2]
        #     else:
        #         main_targets = [min(enemies, key=lambda e: self.calculate_distance(unit, e))] if enemies else []

        #     # 过滤在攻击范围内的目标
        #     valid_targets = [t for t in main_targets
        #                      if self.calculate_distance(unit, t) <= unit.config["attack_radius"]]

        #     # 更新灼燃冷却
        #     if unit.burn_cooldown > 0:
        #         unit.burn_cooldown = max(unit.burn_cooldown - 1 / 30, 0)

        #     # 更新灼燃损伤导致的法抗降低持续时间
        #     if unit.burn_effect_duration > 0:
        #         unit.burn_effect_duration = max(unit.burn_effect_duration - 1 / 30, 0)
        #         if unit.burn_effect_duration <= 0:
        #             unit.current_magic_resist = unit.original_magic_resist

        #     if unit.config.get("effect") == "再生":
        #         unit.health += 250 / 30  # 每秒恢复250，每帧恢复250/30
        #         unit.health = min(unit.health, unit.config["health"])  # 确保不超过最大生命值

        #     if unit.config.get("effect") == "掉血":
        #         unit.health -= 300 / 30  # 每秒掉300，每帧掉300/30
        #         unit.health = min(unit.health, unit.config["health"])  # 确保不超过最大生命值

        #     if not unit.is_alive:
        #         dead_units.append(unit)
        #         continue

        #     # 使用config获取属性
        #     config = unit.config
        #     enemies = [u for u in self.units if u.team != unit.team and u.is_alive]
        #     if not enemies:
        #         continue

        #     target = min(enemies, key=lambda e: self.calculate_distance(unit, e))
        #     distance = self.calculate_distance(unit, target)

        #     # 攻击逻辑使用config
        #     if distance <= config["attack_radius"]:
        #         if unit.attack_cooldown <= 0:
        #             damage = calculate_damage(unit, target)
        #             target.health -= damage

        #             # 溅射效果处理
        #             if config.get("effect") == "溅射":
        #                 # 获取主目标坐标
        #                 main_x, main_y = target.x, target.y
        #                 # 获取所有敌方存活单位
        #                 enemies = [u for u in self.units if u.team != unit.team and u.is_alive]

        #                 for enemy in enemies:
        #                     # 排除主目标自己
        #                     if enemy == target:
        #                         continue
        #                     # 计算与主目标的距离
        #                     dx = enemy.x - main_x
        #                     dy = enemy.y - main_y
        #                     distance = math.hypot(dx, dy)

        #                     # 2格范围内的目标受到同等伤害
        #                     if distance <= 2.0:
        #                         splash_damage = calculate_damage(unit, enemy)
        #                         enemy.health -= splash_damage

        #             if target.config.get("effect") == "反伤":
        #                 resistance = unit.current_magic_resist
        #                 multiplier = (100 - resistance) / 100
        #                 raw_damage = 300 * multiplier
        #                 reflect_damage = max(15, raw_damage)
        #                 unit.health -= reflect_damage

        #             unit.attack_cooldown = config["attack_interval"]
        #         else:
        #             unit.attack_cooldown -= 1 / 30
        #     else:
        #         # 移动逻辑使用config
        #         dx = target.x - unit.x
        #         dy = target.y - unit.y
        #         dist = math.hypot(dx, dy)
        #         if dist == 0:
        #             continue

        #         move_x = (dx / dist) * (config["move_speed"] / 30)
        #         move_y = (dy / dist) * (config["move_speed"] / 30)

        #         new_x = unit.x + move_x
        #         new_y = unit.y + move_y

        #         # 碰撞检测
        #         collision = False
        #         for other in self.units:
        #             if other == unit or not other.is_alive:
        #                 continue
        #             if math.hypot(new_x - other.x, new_y - other.y) < 0.2:
        #                 collision = True
        #                 break
        #         if not collision:
        #             unit.x = new_x
        #             unit.y = new_y

        # # 移除死亡单位
        # for unit in dead_units:
        #     self.units.remove(unit)



        # # 检查胜利条件
        # red_alive = any(u.team == 'red' for u in self.units)
        # blue_alive = any(u.team == 'blue' for u in self.units)

        # if not red_alive and not blue_alive:
        #     self.show_result("平局！")
        # elif not red_alive:
        #     self.show_result("蓝方胜利！")
        # elif not blue_alive:
        #     self.show_result("红方胜利！")
        # else:
        #     interval = max(1, int(33 / self.speed_multiplier))  # 保持最小1ms间隔
        #     self.simulation_id = self.master.after(interval, self.simulate)

    def calculate_distance(self, unit1, unit2):
        return math.hypot(unit1.x - unit2.x, unit1.y - unit2.y)

    def show_result(self, message):
        self.simulating = False
        messagebox.showinfo("游戏结束", message)
        if self.simulation_id:
            self.master.after_cancel(self.simulation_id)

    def clear_sandbox(self):
        self.simulating = False
        if self.simulation_id:
            self.master.after_cancel(self.simulation_id)
        self.units = []
        self.battle_field = Battlefield(self.monster_data)
        self.canvas.delete("all")
        self.draw_grid()
        self.setup_battle_field()

if __name__ == "__main__":
    root = tk.Tk()
    # app = SandboxSimulator(root, {"left": {"1750哥": 4, "标枪恐鱼": 9}, "right": {"狗pro": 44, "机鳄": 8}, "result": "right"})
    app = SandboxSimulator(root, {"left": {"镜神": 7}, "right": {"狂躁珊瑚": 5}, "result": "right"})

    root.mainloop()