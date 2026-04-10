import sqlite3
import hashlib
import tkinter as tk
from tkinter import ttk, messagebox

DB_NAME = "gradebook_gui.db"

APP_TITLE = "Gradebook System - Ms. Carter"

CLASS_NAMES = [
    "Algebra I - Period 1",
    "Algebra II - Period 2",
    "Geometry - Period 3",
    "Pre-Calc - Period 4",
    "AP Calculus - Period 5",
]

STUDENTS_PER_CLASS = 30  # 30 x 5 = 150 total


# ---------------------------
# Helpers
# ---------------------------
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def connect():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def safe_float(text: str):
    try:
        return float(text.strip())
    except Exception:
        return None


# ---------------------------
# DB Setup + Seeding
# ---------------------------
def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('teacher'))
        );

        CREATE TABLE IF NOT EXISTS parent_accounts (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            student_id INTEGER NOT NULL UNIQUE,
            FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS classes (
            class_id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY,
            student_name TEXT NOT NULL,
            class_id INTEGER NOT NULL,
            FOREIGN KEY (class_id) REFERENCES classes(class_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            assignment_name TEXT NOT NULL,
            total_points REAL NOT NULL CHECK(total_points > 0),
            UNIQUE(class_id, assignment_name),
            FOREIGN KEY (class_id) REFERENCES classes(class_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS grades (
            student_id INTEGER NOT NULL,
            assignment_id INTEGER NOT NULL,
            points_earned REAL NOT NULL CHECK (points_earned >= 0),
            PRIMARY KEY (student_id, assignment_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
            FOREIGN KEY (assignment_id) REFERENCES assignments(assignment_id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()


def seed_teacher(conn):
    conn.execute(
        "INSERT OR IGNORE INTO users(username, password_hash, role) VALUES (?,?,?)",
        ("mscarter", hash_pw("Carter@123"), "teacher"),
    )
    conn.commit()


def seed_classes(conn):
    for name in CLASS_NAMES:
        conn.execute("INSERT OR IGNORE INTO classes(class_name) VALUES (?)", (name,))
    conn.commit()


def list_classes(conn):
    cur = conn.execute("SELECT class_id, class_name FROM classes ORDER BY class_id")
    return cur.fetchall()


def get_class_id(conn, class_name: str):
    cur = conn.execute("SELECT class_id FROM classes WHERE class_name = ?", (class_name,))
    row = cur.fetchone()
    return row[0] if row else None


def seed_default_assignments(conn):
    defaults = [
        ("Homework 1", 100.0),
        ("Quiz 1", 50.0),
        ("Unit Test 1", 100.0),
    ]
    for class_id, _ in list_classes(conn):
        for aname, total in defaults:
            conn.execute(
                "INSERT OR IGNORE INTO assignments(class_id, assignment_name, total_points) VALUES (?,?,?)",
                (class_id, aname, total),
            )
    conn.commit()


def seed_students_named(conn):
    cur = conn.execute("SELECT COUNT(*) FROM students")
    if cur.fetchone()[0] > 0:
        return

    first_names = [
        "Ava","Jordan","Maya","Ethan","Noah","Olivia","Amir","Zoe","Camila","Jayden",
        "Imani","Elijah","Sophia","Liam","Aaliyah","Nia","Logan","Ella","Khalil","Aria",
        "Mason","Isabella","Xavier","Mia","Jasmine","Lucas","Gabriel","Layla","Daniel","Hailey",
        "Sienna","Carter","Bryson","Naomi","Makayla","Isaac","Tiana","Anthony","Riley","Savannah",
        "Dylan","Hannah","Miles","Arianna","Devin","Brooklyn","Tristan","Gianna","Malik","Avery",
        "Caleb","Madison","Trinity","Jaden","Faith","Josiah","Sydney","Jorge","Kayla","Micah",
        "Jocelyn","Diego","Cierra","Bryan","Paige","Trey","Kiara","Kehlani","Rafael","Laila",
        "Talia","Rylan","Amina","Sage","Nolan","Alana","Prince","Kinsley","Julius","Selena",
        "Marisol","Andre","Kai","Leilani","Eli","Jalen","Nora","Serena","Aubrey","Jasiah",
        "Megan","Brody","Kobe","Harmony","Kennedy","Darius","Anaya","Brandon","Trevon","Monica",
        "Hayden","Daniella","Kendrick","Rosalie","Cameron","Nevaeh","Kyla","Quinn","Tariq","Asha"
    ]
    last_names = [
        "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez",
        "Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin",
        "Lee","Perez","Thompson","White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson",
        "Walker","Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill","Flores",
        "Green","Adams","Nelson","Baker","Hall","Rivera","Campbell","Mitchell","Carter","Roberts"
    ]

    student_id = 1
    idx = 0

    for class_name in CLASS_NAMES:
        class_id = get_class_id(conn, class_name)
        for _ in range(STUDENTS_PER_CLASS):
            fn = first_names[idx % len(first_names)]
            ln = last_names[(idx * 3) % len(last_names)]
            name = f"{fn} {ln}"
            conn.execute(
                "INSERT INTO students(student_id, student_name, class_id) VALUES (?,?,?)",
                (student_id, name, class_id),
            )
            student_id += 1
            idx += 1

    conn.commit()


def seed_parent_accounts(conn):
    cur = conn.execute("SELECT student_id FROM students ORDER BY student_id")
    students = cur.fetchall()

    for (sid,) in students:
        username = f"parent_{sid:03d}"
        password = f"Parent@{sid}"
        conn.execute(
            "INSERT OR IGNORE INTO parent_accounts(username, password_hash, student_id) VALUES (?,?,?)",
            (username, hash_pw(password), sid),
        )
    conn.commit()


# ---------------------------
# Auth
# ---------------------------
def verify_login(conn, username: str, password: str):
    cur = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    if row and hash_pw(password) == row[0]:
        return {"role": "teacher", "student_id": None}

    cur = conn.execute("SELECT password_hash, student_id FROM parent_accounts WHERE username = ?", (username,))
    row = cur.fetchone()
    if row:
        pw_hash, sid = row
        if hash_pw(password) == pw_hash:
            return {"role": "parent", "student_id": sid}

    return None


# ---------------------------
# Queries
# ---------------------------
def get_students_in_class(conn, class_id: int):
    cur = conn.execute(
        "SELECT student_id, student_name FROM students WHERE class_id = ? ORDER BY student_id",
        (class_id,),
    )
    return cur.fetchall()


def get_assignments_in_class(conn, class_id: int):
    cur = conn.execute(
        "SELECT assignment_id, assignment_name, total_points FROM assignments WHERE class_id = ? ORDER BY assignment_name",
        (class_id,),
    )
    return cur.fetchall()


def get_student_class_id(conn, student_id: int):
    cur = conn.execute("SELECT class_id FROM students WHERE student_id = ?", (student_id,))
    row = cur.fetchone()
    return row[0] if row else None


def get_student_grade_percent(conn, student_id: int):
    class_id = get_student_class_id(conn, student_id)
    if class_id is None:
        return None

    cur = conn.execute("SELECT COALESCE(SUM(total_points),0) FROM assignments WHERE class_id = ?", (class_id,))
    total_possible = float(cur.fetchone()[0])
    if total_possible == 0:
        return 0.0

    cur = conn.execute(
        """
        SELECT COALESCE(SUM(g.points_earned),0)
        FROM grades g
        JOIN assignments a ON a.assignment_id = g.assignment_id
        WHERE g.student_id = ? AND a.class_id = ?
        """,
        (student_id, class_id),
    )
    earned = float(cur.fetchone()[0])

    return round((earned / total_possible) * 100.0, 2)


def get_missing_assignments(conn, student_id: int):
    class_id = get_student_class_id(conn, student_id)
    if class_id is None:
        return []

    cur = conn.execute(
        """
        SELECT a.assignment_name
        FROM assignments a
        WHERE a.class_id = ?
          AND a.assignment_id NOT IN (
              SELECT assignment_id FROM grades WHERE student_id = ?
          )
        ORDER BY a.assignment_name
        """,
        (class_id, student_id),
    )
    return [r[0] for r in cur.fetchall()]


def record_grade(conn, student_id: int, assignment_id: int, points: float):
    cur = conn.execute("SELECT total_points FROM assignments WHERE assignment_id = ?", (assignment_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError("Assignment not found.")
    total = float(row[0])
    if points < 0 or points > total:
        raise ValueError(f"Points must be between 0 and {total}.")

    conn.execute(
        """
        INSERT INTO grades(student_id, assignment_id, points_earned)
        VALUES (?,?,?)
        ON CONFLICT(student_id, assignment_id)
        DO UPDATE SET points_earned = excluded.points_earned
        """,
        (student_id, assignment_id, points),
    )
    conn.commit()


def student_grade_details(conn, student_id: int):
    class_id = get_student_class_id(conn, student_id)
    if class_id is None:
        return []
    cur = conn.execute(
        """
        SELECT a.assignment_name,
               a.total_points,
               (SELECT g.points_earned
                FROM grades g
                WHERE g.student_id = ? AND g.assignment_id = a.assignment_id) AS points_earned
        FROM assignments a
        WHERE a.class_id = ?
        ORDER BY a.assignment_name
        """,
        (student_id, class_id),
    )
    return cur.fetchall()


# ---------------------------
# Assignment CRUD
# ---------------------------
def add_assignment(conn, class_id: int, name: str, total_points: float):
    name = name.strip()
    if not name:
        raise ValueError("Assignment name cannot be empty.")
    if total_points <= 0:
        raise ValueError("Total points must be > 0.")

    conn.execute(
        "INSERT INTO assignments(class_id, assignment_name, total_points) VALUES (?,?,?)",
        (class_id, name, total_points),
    )
    conn.commit()


def update_assignment(conn, assignment_id: int, new_name: str, new_total: float):
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("Assignment name cannot be empty.")
    if new_total <= 0:
        raise ValueError("Total points must be > 0.")

    # Need class_id to enforce UNIQUE(class_id, assignment_name)
    cur = conn.execute("SELECT class_id FROM assignments WHERE assignment_id = ?", (assignment_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError("Assignment not found.")
    class_id = row[0]

    # Check uniqueness within class
    cur = conn.execute(
        "SELECT assignment_id FROM assignments WHERE class_id = ? AND assignment_name = ?",
        (class_id, new_name),
    )
    existing = cur.fetchone()
    if existing and existing[0] != assignment_id:
        raise ValueError("An assignment with that name already exists in this class.")

    conn.execute(
        "UPDATE assignments SET assignment_name = ?, total_points = ? WHERE assignment_id = ?",
        (new_name, new_total, assignment_id),
    )
    conn.commit()


def delete_assignment(conn, assignment_id: int):
    # Grades will delete automatically via ON DELETE CASCADE
    conn.execute("DELETE FROM assignments WHERE assignment_id = ?", (assignment_id,))
    conn.commit()


# ---------------------------
# GUI utilities (Tree + scrollbar)
# ---------------------------
def make_tree_with_scroll(parent, columns, height=18, col_widths=None):
    wrapper = ttk.Frame(parent)
    wrapper.pack(fill="both", expand=True, padx=6, pady=6)

    tree = ttk.Treeview(wrapper, columns=columns, show="headings", height=height)
    vsb = ttk.Scrollbar(wrapper, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)

    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    for c in columns:
        tree.heading(c, text=c)
        w = 160
        if col_widths and c in col_widths:
            w = col_widths[c]
        tree.column(c, width=w)

    return tree


# ---------------------------
# GUI App
# ---------------------------
class GradebookApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x700")

        self.conn = connect()
        init_db(self.conn)
        seed_teacher(self.conn)
        seed_classes(self.conn)
        seed_students_named(self.conn)
        seed_default_assignments(self.conn)
        seed_parent_accounts(self.conn)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_login()

    def on_close(self):
        try:
            self.conn.close()
        except Exception:
            pass
        self.destroy()

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    # ---------------- LOGIN ----------------
    def show_login(self):
        self.clear()

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=APP_TITLE, font=("Segoe UI", 20, "bold")).pack(pady=(0, 10))
        ttk.Label(frame, text="Login", font=("Segoe UI", 14)).pack(pady=(0, 15))

        form = ttk.Frame(frame)
        form.pack()

        ttk.Label(form, text="Username:").grid(row=0, column=0, sticky="e", padx=8, pady=6)
        ttk.Label(form, text="Password:").grid(row=1, column=0, sticky="e", padx=8, pady=6)

        username = ttk.Entry(form, width=30)
        password = ttk.Entry(form, width=30, show="*")
        username.grid(row=0, column=1, pady=6)
        password.grid(row=1, column=1, pady=6)

        hint = (
            "Parent login format: parent_### / Parent@<id>\n"
            "Example: parent_000 / Parent@0"
        )
        ttk.Label(frame, text=hint).pack(pady=12)

        def do_login():
            u = username.get().strip()
            p = password.get().strip()
            result = verify_login(self.conn, u, p)

            if not result:
                messagebox.showerror("Login Failed", "Invalid username or password.")
                return

            if result["role"] == "teacher":
                self.show_teacher_dashboard()
            else:
                self.show_parent_student_view(result["student_id"])

        ttk.Button(frame, text="Login", command=do_login).pack(pady=10)

    # ---------------- TEACHER DASHBOARD ----------------
    def show_teacher_dashboard(self):
        self.clear()

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=APP_TITLE, font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Button(top, text="Logout", command=self.show_login).pack(side="right")

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 10))

        ttk.Label(left, text="Ms. Carter's Classes", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 6))

        class_list = tk.Listbox(left, height=10, width=35)
        class_list.pack(fill="y")

        classes = list_classes(self.conn)
        for cid, cname in classes:
            class_list.insert("end", f"{cid}. {cname}")

        def open_class():
            sel = class_list.curselection()
            if not sel:
                messagebox.showinfo("Select Class", "Please select a class.")
                return
            item = class_list.get(sel[0])
            class_id = int(item.split(".")[0])
            self.show_class_manager(class_id)

        ttk.Button(left, text="Open Class", command=open_class).pack(pady=10, fill="x")

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(right, text="What you can do:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            right,
            text=(
                "• Roster & Submissions (with Search + Scroll)\n"
                "• Record Grades\n"
                "• Progress Report (with Search + Scroll)\n"
                "• Struggling Students (Scroll)\n"
                "• Assignment Manager (Add/Edit/Delete)\n"
                "• Parent read-only access (per student login)\n"
            ),
        ).pack(anchor="w")

    # ---------------- CLASS MANAGER ----------------
    def show_class_manager(self, class_id: int):
        self.clear()

        cur = self.conn.execute("SELECT class_name FROM classes WHERE class_id = ?", (class_id,))
        cname = cur.fetchone()[0]

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=f"{APP_TITLE}  |  {cname}", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Button(top, text="Back", command=self.show_teacher_dashboard).pack(side="right", padx=6)
        ttk.Button(top, text="Logout", command=self.show_login).pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        tab_roster = ttk.Frame(nb)
        tab_record = ttk.Frame(nb)
        tab_report = ttk.Frame(nb)
        tab_struggle = ttk.Frame(nb)
        tab_assign = ttk.Frame(nb)

        nb.add(tab_roster, text="Roster & Submissions")
        nb.add(tab_record, text="Record Grades")
        nb.add(tab_report, text="Progress Report")
        nb.add(tab_struggle, text="Struggling Students")
        nb.add(tab_assign, text="Assignment Manager")

        # Build tabs
        self.build_roster_tab(tab_roster, class_id)
        self.build_record_tab(tab_record, class_id)
        self.build_report_tab(tab_report, class_id)
        self.build_struggling_tab(tab_struggle, class_id)
        self.build_assignment_manager_tab(tab_assign, class_id)

    # ---------------- ROSTER TAB (SEARCH + SCROLL) ----------------
    def build_roster_tab(self, parent, class_id: int):
        ttk.Label(parent, text="Roster + Submission Tracking", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=6)

        search_frame = ttk.Frame(parent, padding=6)
        search_frame.pack(fill="x")
        ttk.Label(search_frame, text="Search (ID or Name):").pack(side="left")

        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side="left", padx=8)

        ttk.Button(search_frame, text="Clear", command=lambda: search_var.set("")).pack(side="left", padx=4)

        cols = ("Student ID", "Student Name", "Current Grade %", "Missing Assignments")
        tree = make_tree_with_scroll(
            parent, cols, height=18,
            col_widths={"Student ID": 120, "Student Name": 320, "Current Grade %": 150, "Missing Assignments": 180}
        )

        def refresh():
            tree.delete(*tree.get_children())

            students = get_students_in_class(self.conn, class_id)
            query = search_var.get().strip().lower()

            for sid, sname in students:
                if query and (query not in str(sid).lower() and query not in sname.lower()):
                    continue

                avg = get_student_grade_percent(self.conn, sid) or 0.0
                missing = get_missing_assignments(self.conn, sid)
                tree.insert("", "end", values=(sid, sname, f"{avg:.2f}", len(missing)))

        ttk.Button(parent, text="Refresh", command=refresh).pack(anchor="e", padx=6, pady=(0, 8))
        search_entry.bind("<KeyRelease>", lambda e: refresh())
        refresh()

    # ---------------- RECORD TAB (Reload assignments) ----------------
    def build_record_tab(self, parent, class_id: int):
        ttk.Label(parent, text="Record Grades", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=6)

        form = ttk.Frame(parent, padding=8)
        form.pack(fill="x")

        ttk.Label(form, text="Student:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        ttk.Label(form, text="Assignment:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        ttk.Label(form, text="Points Earned:").grid(row=2, column=0, sticky="e", padx=6, pady=6)

        student_var = tk.StringVar()
        assign_var = tk.StringVar()
        points_var = tk.StringVar()

        students = get_students_in_class(self.conn, class_id)

        student_box = ttk.Combobox(
            form, textvariable=student_var, state="readonly", width=45,
            values=[f"{sid} - {name}" for sid, name in students]
        )
        student_box.grid(row=0, column=1, padx=6, pady=6, sticky="w")

        assign_box = ttk.Combobox(form, textvariable=assign_var, state="readonly", width=45)
        assign_box.grid(row=1, column=1, padx=6, pady=6, sticky="w")

        points_entry = ttk.Entry(form, textvariable=points_var, width=20)
        points_entry.grid(row=2, column=1, padx=6, pady=6, sticky="w")

        def load_assignments():
            assignments = get_assignments_in_class(self.conn, class_id)
            assign_box["values"] = [f"{aid} - {aname} (/{total})" for aid, aname, total in assignments]
            if assign_box["values"]:
                assign_var.set(assign_box["values"][0])
            else:
                assign_var.set("")

        def save_grade():
            if not student_var.get() or not assign_var.get():
                messagebox.showinfo("Missing Info", "Select a student and an assignment.")
                return
            pts = safe_float(points_var.get())
            if pts is None:
                messagebox.showerror("Error", "Points earned must be a number.")
                return

            try:
                sid = int(student_var.get().split(" - ")[0])
                aid = int(assign_var.get().split(" - ")[0])
                record_grade(self.conn, sid, aid, pts)
                messagebox.showinfo("Saved", "Grade recorded successfully.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(form, text="Save Grade", command=save_grade).grid(row=3, column=1, sticky="w", padx=6, pady=10)
        ttk.Button(form, text="Reload Assignments", command=load_assignments).grid(row=3, column=1, sticky="e", padx=6, pady=10)

        ttk.Label(parent, text="Tip: After editing assignments, click 'Reload Assignments' here.").pack(anchor="w", padx=10, pady=(10, 0))
        load_assignments()

    # ---------------- REPORT TAB (SEARCH + SCROLL) ----------------
    def build_report_tab(self, parent, class_id: int):
        ttk.Label(parent, text="Progress Report (GUI)", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=6)

        search_frame = ttk.Frame(parent, padding=6)
        search_frame.pack(fill="x")
        ttk.Label(search_frame, text="Search (ID or Name):").pack(side="left")

        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side="left", padx=8)

        ttk.Button(search_frame, text="Clear", command=lambda: search_var.set("")).pack(side="left", padx=4)

        cols = ("Student ID", "Student Name", "Current Grade %", "Missing Assignments (names)")
        tree = make_tree_with_scroll(
            parent, cols, height=18,
            col_widths={"Student ID": 120, "Student Name": 320, "Current Grade %": 150, "Missing Assignments (names)": 420}
        )

        def refresh():
            tree.delete(*tree.get_children())

            students = get_students_in_class(self.conn, class_id)
            query = search_var.get().strip().lower()

            for sid, sname in students:
                if query and (query not in str(sid).lower() and query not in sname.lower()):
                    continue

                avg = get_student_grade_percent(self.conn, sid) or 0.0
                missing = get_missing_assignments(self.conn, sid)
                tree.insert("", "end", values=(sid, sname, f"{avg:.2f}", ", ".join(missing) if missing else "None"))

        ttk.Button(parent, text="Refresh Report", command=refresh).pack(anchor="e", padx=6, pady=(0, 8))
        search_entry.bind("<KeyRelease>", lambda e: refresh())
        refresh()

    # ---------------- STRUGGLING TAB (SCROLL) ----------------
    def build_struggling_tab(self, parent, class_id: int):
        ttk.Label(parent, text="Struggling Students", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=6)

        top = ttk.Frame(parent, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Threshold (%):").pack(side="left")

        threshold_var = tk.StringVar(value="70")
        ttk.Entry(top, textvariable=threshold_var, width=8).pack(side="left", padx=8)

        cols = ("Student ID", "Student Name", "Current Grade %", "Missing Count")
        tree = make_tree_with_scroll(
            parent, cols, height=18,
            col_widths={"Student ID": 120, "Student Name": 320, "Current Grade %": 150, "Missing Count": 150}
        )

        def refresh():
            tree.delete(*tree.get_children())

            thresh = safe_float(threshold_var.get())
            if thresh is None:
                messagebox.showerror("Error", "Threshold must be a number.")
                return

            students = get_students_in_class(self.conn, class_id)
            for sid, sname in students:
                avg = get_student_grade_percent(self.conn, sid) or 0.0
                missing = get_missing_assignments(self.conn, sid)
                if avg < thresh:
                    tree.insert("", "end", values=(sid, sname, f"{avg:.2f}", len(missing)))

        ttk.Button(top, text="Refresh", command=refresh).pack(side="left", padx=10)
        refresh()

    # ---------------- ASSIGNMENT MANAGER TAB (Add/Edit/Delete + Scroll) ----------------
    def build_assignment_manager_tab(self, parent, class_id: int):
        ttk.Label(parent, text="Assignment Manager", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=6)
        ttk.Label(parent, text="Add / Edit / Delete assignments for this class. Deleting an assignment also deletes its recorded grades.").pack(anchor="w", padx=6)

        cols = ("Assignment ID", "Assignment Name", "Total Points")
        tree = make_tree_with_scroll(
            parent, cols, height=16,
            col_widths={"Assignment ID": 120, "Assignment Name": 420, "Total Points": 140}
        )

        controls = ttk.Frame(parent, padding=8)
        controls.pack(fill="x")

        ttk.Label(controls, text="Name:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        ttk.Label(controls, text="Total Points:").grid(row=0, column=2, sticky="e", padx=6, pady=6)

        name_var = tk.StringVar()
        total_var = tk.StringVar()

        name_entry = ttk.Entry(controls, textvariable=name_var, width=40)
        total_entry = ttk.Entry(controls, textvariable=total_var, width=12)

        name_entry.grid(row=0, column=1, sticky="w", padx=6, pady=6)
        total_entry.grid(row=0, column=3, sticky="w", padx=6, pady=6)

        def refresh():
            tree.delete(*tree.get_children())
            for aid, aname, total in get_assignments_in_class(self.conn, class_id):
                tree.insert("", "end", values=(aid, aname, total))

        def clear_form():
            name_var.set("")
            total_var.set("")
            tree.selection_remove(tree.selection())

        def on_select(_event=None):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0], "values")
            # vals: (id, name, total)
            name_var.set(vals[1])
            total_var.set(str(vals[2]))

        tree.bind("<<TreeviewSelect>>", on_select)

        def do_add():
            name = name_var.get().strip()
            total = safe_float(total_var.get())
            if total is None:
                messagebox.showerror("Error", "Total points must be a number.")
                return
            try:
                add_assignment(self.conn, class_id, name, total)
                refresh()
                clear_form()
                messagebox.showinfo("Added", "Assignment added.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        def do_edit():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Select", "Select an assignment to edit.")
                return
            assignment_id = int(tree.item(sel[0], "values")[0])
            name = name_var.get().strip()
            total = safe_float(total_var.get())
            if total is None:
                messagebox.showerror("Error", "Total points must be a number.")
                return
            try:
                update_assignment(self.conn, assignment_id, name, total)
                refresh()
                messagebox.showinfo("Updated", "Assignment updated.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        def do_delete():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Select", "Select an assignment to delete.")
                return
            assignment_id = int(tree.item(sel[0], "values")[0])
            aname = tree.item(sel[0], "values")[1]
            if not messagebox.askyesno("Confirm Delete", f"Delete '{aname}'?\nThis will also remove all grades for it."):
                return
            try:
                delete_assignment(self.conn, assignment_id)
                refresh()
                clear_form()
                messagebox.showinfo("Deleted", "Assignment deleted.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(controls, text="Add", command=do_add).grid(row=1, column=1, sticky="w", padx=6, pady=6)
        ttk.Button(controls, text="Edit Selected", command=do_edit).grid(row=1, column=1, sticky="e", padx=6, pady=6)
        ttk.Button(controls, text="Delete Selected", command=do_delete).grid(row=1, column=3, sticky="w", padx=6, pady=6)
        ttk.Button(controls, text="Clear", command=clear_form).grid(row=1, column=3, sticky="e", padx=6, pady=6)

        ttk.Button(parent, text="Refresh Assignments List", command=refresh).pack(anchor="e", padx=6, pady=(0, 8))
        refresh()

    # ---------------- PARENT VIEW (SCROLL) ----------------
    def show_parent_student_view(self, student_id: int):
        self.clear()

        cur = self.conn.execute("SELECT student_name FROM students WHERE student_id = ?", (student_id,))
        row = cur.fetchone()
        if not row:
            messagebox.showerror("Error", "Student not found.")
            self.show_login()
            return

        sname = row[0]

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=f"{APP_TITLE}  |  Parent Portal (Read-only)", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Button(top, text="Logout", command=self.show_login).pack(side="right")

        avg = get_student_grade_percent(self.conn, student_id) or 0.0
        missing = get_missing_assignments(self.conn, student_id)

        summary = ttk.Frame(self, padding=10)
        summary.pack(fill="x")
        ttk.Label(summary, text=f"Student: {sname} (ID: {student_id})", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(summary, text=f"Current Grade: {avg:.2f}%").pack(anchor="w")
        ttk.Label(summary, text="Missing Assignments: " + (", ".join(missing) if missing else "None")).pack(anchor="w")

        ttk.Label(self, text="Assignment Details", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=10, pady=(8, 0))

        cols = ("Assignment", "Total Points", "Points Earned")
        tree = make_tree_with_scroll(
            self, cols, height=18,
            col_widths={"Assignment": 420, "Total Points": 150, "Points Earned": 200}
        )

        tree.delete(*tree.get_children())
        for aname, total, earned in student_grade_details(self.conn, student_id):
            tree.insert("", "end", values=(aname, total, earned if earned is not None else "Not Submitted"))


def main():
    app = GradebookApp()
    app.mainloop()


if __name__ == "__main__":
    main()