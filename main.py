
import os
import sqlite3
from calendar import monthrange
from datetime import date, datetime, timedelta

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex


APP_TITLE = "Рабочий календарь"
DB_NAME = "work_calendar.db"

MONTHS = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

RED = "#D94A4A"          # выходной
DARK = "#17191E"
PANEL = "#22252C"
PANEL_2 = "#2B2F38"
TEXT = "#F3F4F6"
MUTED = "#A9AFBC"
ACCENT = "#4E89FF"


def hex_color(value, alpha=1.0):
    return get_color_from_hex(value + ("%02X" % int(alpha * 255)))


def shift_hours(start_time, end_time):
    """Return duration in hours, including overnight shifts."""
    sh, sm = map(int, start_time.split(":"))
    eh, em = map(int, end_time.split(":"))
    start = sh * 60 + sm
    end = eh * 60 + em
    if end <= start:
        end += 24 * 60
    return (end - start) / 60.0


class CardButton(Button):
    def __init__(self, fill="#2B2F38", **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self._fill = fill
        with self.canvas.before:
            Color(*hex_color(fill))
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

    def _sync_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size


class DayCell(Button):
    def __init__(self, app, day_date, record, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.day_date = day_date
        self.record = record
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = hex_color(TEXT)
        self.markup = True
        self.font_size = dp(11)
        self.halign = "center"
        self.valign = "middle"
        self.padding = (dp(1), dp(3))
        self.bind(on_release=lambda *_: self.app.apply_shift(self.day_date))

        color = record["color"] if record and record["color"] else RED
        with self.canvas.before:
            Color(*hex_color(color))
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(7)])
        self.bind(pos=self._sync_bg, size=self._sync_bg)
        self.refresh()

    def _sync_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def refresh(self):
        day_num = self.day_date.day
        if self.record:
            hours = float(self.record["hours"])
            salary = float(self.record["salary"])
            if hours > 0:
                self.text = f"[b]{day_num}[/b]\n{hours:g}ч · {salary:.0f}р"
            else:
                self.text = f"[b]{day_num}[/b]"
        else:
            self.text = f"[b]{day_num}[/b]"
        if self.day_date == date.today():
            self.text = f"[b]• {self.day_date.day}[/b]\n" + (
                self.text.split("\n", 1)[1] if "\n" in self.text else ""
            )


class WorkCalendarDB:
    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._create()

    def _create(self):
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                color TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workdays (
                date TEXT PRIMARY KEY,
                shift_id INTEGER,
                start_time TEXT,
                end_time TEXT,
                hours REAL NOT NULL DEFAULT 0,
                rate REAL NOT NULL DEFAULT 0,
                salary REAL NOT NULL DEFAULT 0,
                color TEXT NOT NULL DEFAULT '#D94A4A',
                FOREIGN KEY (shift_id) REFERENCES shifts(id)
            );

            CREATE TABLE IF NOT EXISTS pay_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pay_day INTEGER NOT NULL,
                period_start INTEGER NOT NULL,
                period_end INTEGER NOT NULL
            );
            """
        )
        if self.get_setting("hourly_rate") is None:
            self.set_setting("hourly_rate", "0")
        self.conn.commit()

    def get_setting(self, key, default=None):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        self.conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        self.conn.commit()

    def shifts(self):
        return self.conn.execute("SELECT * FROM shifts ORDER BY id").fetchall()

    def add_shift(self, name, start_time, end_time, color):
        self.conn.execute(
            "INSERT INTO shifts(name,start_time,end_time,color) VALUES(?,?,?,?)",
            (name, start_time, end_time, color),
        )
        self.conn.commit()

    def delete_shift(self, shift_id):
        self.conn.execute("DELETE FROM shifts WHERE id=?", (shift_id,))
        self.conn.commit()

    def get_day(self, iso_date):
        return self.conn.execute(
            "SELECT * FROM workdays WHERE date=?", (iso_date,)
        ).fetchone()

    def apply_shift(self, iso_date, shift):
        rate = float(self.get_setting("hourly_rate", "0") or 0)
        hours = shift_hours(shift["start_time"], shift["end_time"])
        salary = hours * rate
        self.conn.execute(
            """
            INSERT INTO workdays(date,shift_id,start_time,end_time,hours,rate,salary,color)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(date) DO UPDATE SET
                shift_id=excluded.shift_id,
                start_time=excluded.start_time,
                end_time=excluded.end_time,
                hours=excluded.hours,
                rate=excluded.rate,
                salary=excluded.salary,
                color=excluded.color
            """,
            (
                iso_date, shift["id"], shift["start_time"], shift["end_time"],
                hours, rate, salary, shift["color"]
            ),
        )
        self.conn.commit()

    def clear_day(self, iso_date):
        self.conn.execute(
            """
            INSERT INTO workdays(date,shift_id,start_time,end_time,hours,rate,salary,color)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(date) DO UPDATE SET
                shift_id=NULL, start_time=NULL, end_time=NULL,
                hours=0, salary=0, color=?
            """,
            (iso_date, None, None, None, 0, 0, 0, RED, RED),
        )
        self.conn.commit()

    def month_summary(self, year, month):
        start = f"{year:04d}-{month:02d}-01"
        end = f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}"
        row = self.conn.execute(
            """
            SELECT
                SUM(CASE WHEN hours > 0 THEN 1 ELSE 0 END) AS days,
                COALESCE(SUM(hours),0) AS hours,
                COALESCE(SUM(salary),0) AS salary
            FROM workdays
            WHERE date BETWEEN ? AND ?
            """,
            (start, end),
        ).fetchone()
        return int(row["days"] or 0), float(row["hours"] or 0), float(row["salary"] or 0)

    def pay_rules(self):
        return self.conn.execute(
            "SELECT * FROM pay_rules ORDER BY pay_day, period_start"
        ).fetchall()

    def add_pay_rule(self, pay_day, period_start, period_end):
        self.conn.execute(
            "INSERT INTO pay_rules(pay_day,period_start,period_end) VALUES(?,?,?)",
            (pay_day, period_start, period_end),
        )
        self.conn.commit()

    def delete_pay_rule(self, rule_id):
        self.conn.execute("DELETE FROM pay_rules WHERE id=?", (rule_id,))
        self.conn.commit()


class ShiftDialog(Popup):
    def __init__(self, app, **kwargs):
        super().__init__(
            title="Новая смена",
            size_hint=(0.92, None),
            height=dp(430),
            auto_dismiss=False,
            **kwargs,
        )
        self.app = app
        box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))

        self.name = TextInput(hint_text="Название, например: День", multiline=False)
        self.start = TextInput(text="10:00", hint_text="Начало: ЧЧ:ММ", multiline=False)
        self.end = TextInput(text="22:00", hint_text="Конец: ЧЧ:ММ", multiline=False)
        self.color = TextInput(text="#FF9800", hint_text="Цвет HEX, например #FF9800", multiline=False)

        for title, widget in [
            ("Название", self.name),
            ("Начало", self.start),
            ("Конец", self.end),
            ("Цвет", self.color),
        ]:
            box.add_widget(Label(text=title, color=hex_color(MUTED), size_hint_y=None, height=dp(24)))
            box.add_widget(widget)

        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        cancel = CardButton(text="Отмена", fill=PANEL_2)
        save = CardButton(text="Добавить", fill=ACCENT)
        cancel.bind(on_release=lambda *_: self.dismiss())
        save.bind(on_release=self.save)
        buttons.add_widget(cancel)
        buttons.add_widget(save)
        box.add_widget(buttons)
        self.content = box

    def save(self, *_):
        try:
            datetime.strptime(self.start.text.strip(), "%H:%M")
            datetime.strptime(self.end.text.strip(), "%H:%M")
            color = self.color.text.strip().upper()
            if len(color) != 7 or not color.startswith("#"):
                raise ValueError
            if not self.name.text.strip():
                raise ValueError
            self.app.db.add_shift(
                self.name.text.strip(),
                self.start.text.strip(),
                self.end.text.strip(),
                color,
            )
            self.app.rebuild()
            self.dismiss()
        except ValueError:
            self.app.info("Проверь название, время и HEX-цвет.")


class SettingsPopup(Popup):
    def __init__(self, app, **kwargs):
        super().__init__(
            title="Настройки",
            size_hint=(0.95, 0.90),
            auto_dismiss=True,
            **kwargs,
        )
        self.app = app
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))

        rate_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        rate_row.add_widget(Label(text="ЗП за час", color=hex_color(TEXT)))
        self.rate = TextInput(
            text=str(app.db.get_setting("hourly_rate", "0")),
            multiline=False,
            input_filter="float",
            size_hint_x=0.48,
        )
        rate_row.add_widget(self.rate)
        save_rate = CardButton(text="Сохранить", fill=ACCENT, size_hint_x=0.32)
        save_rate.bind(on_release=self.save_rate)
        rate_row.add_widget(save_rate)
        root.add_widget(rate_row)

        root.add_widget(Label(
            text="Важно: изменение ставки не пересчитывает уже назначенные дни.",
            color=hex_color(MUTED), size_hint_y=None, height=dp(38)
        ))

        root.add_widget(Label(
            text="Правила начисления зарплаты", color=hex_color(TEXT),
            size_hint_y=None, height=dp(30)
        ))

        scroll = ScrollView()
        self.rules_box = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        self.rules_box.bind(minimum_height=self.rules_box.setter("height"))
        scroll.add_widget(self.rules_box)
        root.add_widget(scroll)

        add_rule = CardButton(text="Добавить период начисления", fill=PANEL_2, size_hint_y=None, height=dp(50))
        add_rule.bind(on_release=self.add_rule)
        root.add_widget(add_rule)

        close = CardButton(text="Закрыть", fill=ACCENT, size_hint_y=None, height=dp(50))
        close.bind(on_release=lambda *_: self.dismiss())
        root.add_widget(close)

        self.content = root
        self.refresh_rules()

    def save_rate(self, *_):
        try:
            rate = float(self.rate.text.replace(",", "."))
            if rate < 0:
                raise ValueError
            self.app.db.set_setting("hourly_rate", rate)
            self.app.info("Ставка сохранена. Старые дни не изменились.")
        except ValueError:
            self.app.info("Некорректная ставка.")

    def refresh_rules(self):
        self.rules_box.clear_widgets()
        rules = self.app.db.pay_rules()
        if not rules:
            self.rules_box.add_widget(Label(
                text="Правил пока нет. Приложение ничего не добавляет автоматически.",
                color=hex_color(MUTED), size_hint_y=None, height=dp(60)
            ))
            return
        for rule in rules:
            row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
            row.add_widget(Label(
                text=f"День {rule['pay_day']}: период {rule['period_start']}–{rule['period_end']}",
                color=hex_color(TEXT)
            ))
            delete = CardButton(text="Удалить", fill=RED, size_hint_x=0.25)
            delete.bind(on_release=lambda _, rid=rule["id"]: self.delete_rule(rid))
            row.add_widget(delete)
            self.rules_box.add_widget(row)

    def add_rule(self, *_):
        content = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        pay_day = TextInput(hint_text="День выплаты, например 20", input_filter="int", multiline=False)
        start = TextInput(hint_text="С какого дня, например 1", input_filter="int", multiline=False)
        end = TextInput(hint_text="По какой день, например 15", input_filter="int", multiline=False)
        for w in (pay_day, start, end):
            content.add_widget(w)

        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        cancel = CardButton(text="Отмена", fill=PANEL_2)
        save = CardButton(text="Добавить", fill=ACCENT)
        buttons.add_widget(cancel)
        buttons.add_widget(save)
        content.add_widget(buttons)

        pop = Popup(title="Период начисления", content=content, size_hint=(0.9, None), height=dp(320), auto_dismiss=False)
        cancel.bind(on_release=lambda *_: pop.dismiss())

        def do_save(_):
            try:
                pd, s, e = int(pay_day.text), int(start.text), int(end.text)
                if not (1 <= pd <= 31 and 1 <= s <= 31 and 1 <= e <= 31 and s <= e):
                    raise ValueError
                self.app.db.add_pay_rule(pd, s, e)
                pop.dismiss()
                self.refresh_rules()
            except ValueError:
                self.app.info("Введите дни от 1 до 31, период: начало ≤ конец.")

        save.bind(on_release=do_save)
        pop.open()

    def delete_rule(self, rule_id):
        self.app.db.delete_pay_rule(rule_id)
        self.refresh_rules()


class WorkCalendarApp(App):
    def build(self):
        self.title = APP_TITLE
        Window.clearcolor = hex_color(DARK)
        self.db = WorkCalendarDB(os.path.join(self.user_data_dir, DB_NAME))
        now = date.today()
        self.year = now.year
        self.month = now.month
        self.selected_shift_id = None

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        header = BoxLayout(size_hint_y=None, height=dp(58), spacing=dp(8))
        self.stats = Label(color=hex_color(TEXT), font_size=dp(15), halign="left", valign="middle")
        self.stats.bind(size=lambda *_: setattr(self.stats, "text_size", self.stats.size))
        header.add_widget(self.stats)

        settings_btn = CardButton(text="⚙", fill=PANEL_2, size_hint_x=None, width=dp(52))
        settings_btn.bind(on_release=self.open_settings)
        header.add_widget(settings_btn)
        root.add_widget(header)

        nav = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        prev_btn = CardButton(text="‹", fill=PANEL_2, size_hint_x=None, width=dp(52))
        next_btn = CardButton(text="›", fill=PANEL_2, size_hint_x=None, width=dp(52))
        month_btn = CardButton(fill=PANEL_2)
        self.month_button = month_btn
        prev_btn.bind(on_release=lambda *_: self.change_month(-1))
        next_btn.bind(on_release=lambda *_: self.change_month(1))
        nav.add_widget(prev_btn)
        nav.add_widget(month_btn)
        nav.add_widget(next_btn)
        root.add_widget(nav)

        self.shift_scroll = ScrollView(
            size_hint_y=None, height=dp(52),
            do_scroll_x=True, do_scroll_y=False, bar_width=0
        )
        self.shift_bar = BoxLayout(
            orientation="horizontal", spacing=dp(7), padding=(0, dp(2)),
            size_hint_x=None
        )
        self.shift_bar.bind(minimum_width=self.shift_bar.setter("width"))
        self.shift_scroll.add_widget(self.shift_bar)
        root.add_widget(self.shift_scroll)

        self.grid = GridLayout(cols=7, spacing=dp(4), padding=dp(2))
        root.add_widget(self.grid)

        bottom = Label(
            text="Выберите маркер смены сверху и нажмите на день. Нажатие на красный маркер — выходной.",
            color=hex_color(MUTED), font_size=dp(11), size_hint_y=None, height=dp(32)
        )
        root.add_widget(bottom)

        self.rebuild()
        return root

    def info(self, text):
        Popup(
            title="Рабочий календарь",
            content=Label(text=text, color=hex_color(TEXT)),
            size_hint=(0.85, None),
            height=dp(180)
        ).open()

    def open_settings(self, *_):
        SettingsPopup(self).open()

    def open_shift_dialog(self, *_):
        ShiftDialog(self).open()

    def change_month(self, delta):
        month = self.month + delta
        year = self.year
        if month < 1:
            month, year = 12, year - 1
        elif month > 12:
            month, year = 1, year + 1
        self.month, self.year = month, year
        self.rebuild()

    def select_shift(self, shift_id):
        self.selected_shift_id = shift_id
        self.refresh_shift_bar()

    def apply_shift(self, day):
        iso = day.isoformat()
        if self.selected_shift_id is None:
            self.db.clear_day(iso)
        else:
            shift = next((s for s in self.db.shifts() if s["id"] == self.selected_shift_id), None)
            if shift:
                self.db.apply_shift(iso, shift)
        self.rebuild()

    def refresh_shift_bar(self):
        self.shift_bar.clear_widgets()

        add = CardButton(text="+ Смена", fill=ACCENT, size_hint_x=None, width=dp(110))
        add.bind(on_release=self.open_shift_dialog)
        self.shift_bar.add_widget(add)

        off = CardButton(text="🔴 Выходной", fill=RED, size_hint_x=None, width=dp(120))
        if self.selected_shift_id is None:
            off.text = "✓ Выходной"
        off.bind(on_release=lambda *_: self.select_shift(None))
        self.shift_bar.add_widget(off)

        for shift in self.db.shifts():
            title = f"{shift['name']} {shift['start_time']}-{shift['end_time']}"
            if shift["id"] == self.selected_shift_id:
                title = "✓ " + title
            b = CardButton(text=title, fill=shift["color"], size_hint_x=None, width=dp(160))
            b.bind(on_release=lambda _, sid=shift["id"]: self.select_shift(sid))
            self.shift_bar.add_widget(b)

    def rebuild(self, *_):
        self.month_button.text = f"{MONTHS[self.month - 1]} {self.year}"
        days_count, hours, salary = self.db.month_summary(self.year, self.month)
        self.stats.text = (
            f"[b]{MONTHS[self.month - 1]}[/b] — "
            f"{days_count}д, {hours:g}ч, {salary:.0f}р"
        )
        self.stats.markup = True

        self.refresh_shift_bar()
        self.grid.clear_widgets()

        for weekday in WEEKDAYS:
            self.grid.add_widget(Label(
                text=weekday, color=hex_color(MUTED), size_hint_y=None,
                height=dp(26), font_size=dp(11)
            ))

        first = date(self.year, self.month, 1)
        start_offset = first.weekday()
        total = monthrange(self.year, self.month)[1]
        rows = 6
        total_cells = rows * 7

        for i in range(total_cells):
            day_num = i - start_offset + 1
            if 1 <= day_num <= total:
                d = date(self.year, self.month, day_num)
                rec = self.db.get_day(d.isoformat())
                cell = DayCell(self, d, rec)
                self.grid.add_widget(cell)
            else:
                self.grid.add_widget(Label(text=""))

        Clock.schedule_once(self._fix_grid_height, 0)

    def _fix_grid_height(self, *_):
        pass


if __name__ == "__main__":
    WorkCalendarApp().run()
