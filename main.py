import json
from datetime import datetime, timedelta
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.storage.jsonstore import JsonStore
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.utils import platform

class GradientBackground(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self.rect = Rectangle(size=self.size, pos=self.pos)
            self.bind(pos=self.update_rect, size=self.update_rect)
            self.update_rect()

    def update_rect(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.8, 0.2, 0.2, 1)  # Start color (redish)
            self.rect = Rectangle(size=self.size, pos=self.pos)
            Color(0.1, 0.1, 0.5, 1)  # End color (blueish)
            self.rect = Rectangle(size=self.size, pos=self.pos, source='gradient.png')  # Use a gradient image if available

    def add_widget(self, widget, index=0):
        super().add_widget(widget, index=index)
        self.update_rect()

class HoverButton(Button):
    def on_enter(self, *args):
        self.background_color = (0, 0.7, 1, 1)  # Change color on hover
        self.text = f'😃 {self.text.strip()}'

    def on_leave(self, *args):
        self.background_color = (0.2, 0.6, 0.8, 1)
        self.text = self.text.strip()[1:].strip()

class WorkCounterApp(App):
    def build(self):
        self.title = 'WorkCounter'
        self.store = JsonStore('workcounter.json')

        # Create the root layout with gradient background
        root = GradientBackground(orientation='vertical', padding=10, spacing=10)

        # Add UI elements to the root layout
        title_label = Label(text='WorkCounter', font_size='24sp', size_hint_y=None, height='48dp', color=(1, 1, 1, 1))
        root.add_widget(title_label)

        self.check_in_label = Label(text='Check-in Time: Not available', halign='left', color=(1, 1, 1, 1))
        self.check_out_label = Label(text='Check-out Time: Not available', halign='left', color=(1, 1, 1, 1))
        self.timer_label = Label(text='Time since clock-in: 0h 0m 0s', halign='left', color=(1, 1, 1, 1))
        root.add_widget(self.check_in_label)
        root.add_widget(self.check_out_label)
        root.add_widget(self.timer_label)

        # ScrollView for logs
        self.logs_container = BoxLayout(orientation='vertical', size_hint_y=None)
        scroll_view = ScrollView(size_hint=(1, 0.5))
        scroll_view.add_widget(self.logs_container)
        root.add_widget(scroll_view)

        # Buttons
        clock_in_button = HoverButton(text='Clock In ⏰', size_hint_y=None, height='48dp')
        clock_in_button.bind(on_press=self.clock_in)
        root.add_widget(clock_in_button)

        clock_out_button = HoverButton(text='Clock Out ⌛', size_hint_y=None, height='48dp')
        clock_out_button.bind(on_press=self.clock_out)
        root.add_widget(clock_out_button)

        calculate_exit_button = HoverButton(text='Calculate Exit Time 🕒', size_hint_y=None, height='48dp')
        calculate_exit_button.bind(on_press=self.calculate_exit_time)
        root.add_widget(calculate_exit_button)

        exit_button = HoverButton(text='Exit 🚪', size_hint_y=None, height='48dp')
        exit_button.bind(on_press=self.stop)
        root.add_widget(exit_button)

        self.load_data()

        # Start the timer to update elapsed time every second
        Clock.schedule_interval(self.update_timer, 1)

        return root

    def clock_in(self, instance):
        clock_in_time = datetime.now().isoformat()
        times = self.store.get('check_in_out_times')['times'] if self.store.exists('check_in_out_times') else []
        times.append({'type': 'in', 'time': clock_in_time})
        self.store.put('clock_in_time', time=clock_in_time)
        self.store.put('check_in_out_times', times=times)
        self.check_in_label.text = f"Clocked in at {datetime.fromisoformat(clock_in_time).strftime('%I:%M %p')}"
        self.check_out_label.text = "Check-out Time: Not available"
        self.update_check_in_out_times(times)

    def clock_out(self, instance):
        if not self.store.exists('clock_in_time'):
            self.check_out_label.text = 'You need to clock in first.'
            return

        clock_out_time = datetime.now().isoformat()
        clock_in_time = datetime.fromisoformat(self.store.get('clock_in_time')['time'])
        time_worked = datetime.fromisoformat(clock_out_time) - clock_in_time

        if time_worked.total_seconds() < 0:
            time_worked += timedelta(days=1)

        times = self.store.get('check_in_out_times')['times']
        times.append({'type': 'out', 'time': clock_out_time})
        total_worked_seconds = self.store.get('total_worked_seconds')['seconds'] if self.store.exists('total_worked_seconds') else 0
        total_worked_seconds += time_worked.total_seconds()
        self.store.put('total_worked_seconds', seconds=total_worked_seconds)
        self.store.put('check_in_out_times', times=times)
        self.store.delete('clock_in_time')

        self.check_out_label.text = f"Clocked out at {datetime.fromisoformat(clock_out_time).strftime('%I:%M %p')}\nWorked this session: {self.format_time_interval(time_worked.total_seconds())}\nTotal worked time: {self.format_time_interval(total_worked_seconds)}"
        self.update_check_in_out_times(times)

    def calculate_exit_time(self, instance):
        required_seconds = 8.5 * 3600
        total_worked_seconds = self.store.get('total_worked_seconds')['seconds'] if self.store.exists('total_worked_seconds') else 0

        if total_worked_seconds >= required_seconds:
            self.check_out_label.text = 'You have already met the required work hours.'
            return

        remaining_seconds = required_seconds - total_worked_seconds
        if not self.store.exists('clock_in_time'):
            self.check_out_label.text = 'You need to clock in first.'
            return

        clock_in_time = datetime.fromisoformat(self.store.get('clock_in_time')['time'])
        exit_time = clock_in_time + timedelta(seconds=remaining_seconds)
        self.check_out_label.text = f"Remaining time to work: {self.format_time_interval(remaining_seconds)}\nExpected exit time: {exit_time.strftime('%I:%M %p')}"

    def update_timer(self, dt):
        if self.store.exists('clock_in_time'):
            clock_in_time = datetime.fromisoformat(self.store.get('clock_in_time')['time'])
            now = datetime.now()
            elapsed = now - clock_in_time

            if elapsed.total_seconds() < 0:
                elapsed += timedelta(days=1)

            self.timer_label.text = f"Time since clock-in: {self.format_time_interval(elapsed.total_seconds())}"
        else:
            self.timer_label.text = 'Time since clock-in: 0h 0m 0s'

    def format_time_interval(self, interval):
        hours = int(interval // 3600)
        minutes = int((interval % 3600) // 60)
        seconds = int(interval % 60)
        return f"{hours}h {minutes}m {seconds}s"

    def update_check_in_out_times(self, times):
        self.logs_container.clear_widgets()
        for time_entry in times:
            time_string = datetime.fromisoformat(time_entry['time']).strftime('%I:%M %p')
            type_str = 'Clocked in' if time_entry['type'] == 'in' else 'Clocked out'
            entry = Label(text=f"{type_str} at {time_string}", size_hint_y=None, height='30dp', color=(1, 1, 1, 1))
            self.logs_container.add_widget(entry)

    def load_data(self):
        if self.store.exists('check_in_out_times'):
            times = self.store.get('check_in_out_times')['times']
            self.update_check_in_out_times(times)

        if self.store.exists('clock_in_time'):
            clock_in_time = self.store.get('clock_in_time')['time']
            self.check_in_label.text = f"Clocked in at {datetime.fromisoformat(clock_in_time).strftime('%I:%M %p')}"
        else:
            self.check_in_label.text = "Check-in Time: Not available"

        if self.store.exists('total_worked_seconds'):
            total_worked_seconds = self.store.get('total_worked_seconds')['seconds']
            self.check_out_label.text = f"Total worked time: {self.format_time_interval(total_worked_seconds)}"
        else:
            self.check_out_label.text = "Check-out Time: Not available"

if __name__ == '__main__':
    WorkCounterApp().run()
