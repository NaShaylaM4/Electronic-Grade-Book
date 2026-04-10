import sqlite3, hashlib, tkinter as tk
from tkinter import ttk, messagebox
#
# Created By: Anderson Peterkin, Na'Shayla McIntosh, Elijah Gordon
#
# ------------------------------------------------------------
# Electronic Gradebook System (Python + SQLite + Tkinter GUI)
# Teacher login:  mscarter / Carter@123
# Parent login:   parent_### / Parent@<student_id>  (read-only for one student)
#
# Database file:  gradebook_gui.db
# NOTE: The DB file is created automatically in the SAME folder as this .py file.
# To reset the system, delete gradebook_gui.db and run again.
#
# Features:
# - 5 classes (Ms. Carter’s schedule)
# - 30 students per class (150 total)
# - Search roster by student ID or name
# - Record grades (insert/update)
# - Progress report screen
# - Struggling students screen (threshold-based)
# - Assignment Manager (add/edit/delete assignments per class)
# - Parent portal (view only their child)
# ------------------------------------------------------------
DB="gradebook_gui.db"
APP="Gradebook System - Ms. Carter"
CLASSES=[
    "Algebra I - Period 1","Algebra II - Period 2","Geometry - Period 3","Pre-Calc - Period 4","AP Calculus - Period 5"
]
PER_CLASS=30

def h(p): return hashlib.sha256(p.encode()).hexdigest()
def conn():
    c=sqlite3.connect(DB); c.execute("PRAGMA foreign_keys=ON"); return c
def fnum(s):
    try: return float(s.strip())
    except: return None

# ---------------------------
# SQLite Database Schema Setup
# ---------------------------
# Tables:
# users            -> teacher login
# parent_accounts  -> parent login tied to exactly one student
# classes          -> Ms. Carter’s 5 classes
# students         -> roster: students belong to one class
# assignments      -> assignments belong to a class (unique per class)
# grades           -> student scores on assignments (composite key)
def init(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY,password_hash TEXT,role TEXT CHECK(role IN('teacher')));
    CREATE TABLE IF NOT EXISTS classes(class_id INTEGER PRIMARY KEY AUTOINCREMENT,class_name TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS students(student_id INTEGER PRIMARY KEY,student_name TEXT NOT NULL,class_id INTEGER NOT NULL,
        FOREIGN KEY(class_id) REFERENCES classes(class_id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS assignments(assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,class_id INTEGER NOT NULL,
        assignment_name TEXT NOT NULL,total_points REAL NOT NULL CHECK(total_points>0),
        UNIQUE(class_id,assignment_name),FOREIGN KEY(class_id) REFERENCES classes(class_id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS grades(student_id INTEGER NOT NULL,assignment_id INTEGER NOT NULL,points_earned REAL NOT NULL CHECK(points_earned>=0),
        PRIMARY KEY(student_id,assignment_id),
        FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE,
        FOREIGN KEY(assignment_id) REFERENCES assignments(assignment_id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS parent_accounts(username TEXT PRIMARY KEY,password_hash TEXT NOT NULL,student_id INTEGER UNIQUE NOT NULL,
        FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE);
    """); c.commit()

# ---------------------------
# Seed Data (Demo Setup)
# ---------------------------
# Inserts demo data ONLY if it doesn’t already exist:
# - Creates Ms. Carter teacher account
# - Creates 5 classes
# - Creates 150 students (30 per class)
# - Creates default assignments for each class
# - Creates one parent login per student
# Uses INSERT OR IGNORE to prevent duplicate rows if you run again.
def seed(c):
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,?)",("mscarter",h("Carter@123"),"teacher"))
    for n in CLASSES: c.execute("INSERT OR IGNORE INTO classes(class_name) VALUES (?)",(n,))
    c.commit()
    
    # Only seed students if student table is empty
    if c.execute("SELECT COUNT(*) FROM students").fetchone()[0]==0:
        first=["Ava","Jordan","Maya","Ethan","Noah","Olivia","Amir","Zoe","Camila","Jayden",
               "Imani","Elijah","Sophia","Liam","Aaliyah","Nia","Logan","Ella","Khalil","Aria",
               "Mason","Isabella","Xavier","Mia","Jasmine","Lucas","Gabriel","Layla","Daniel","Hailey"]
        last=["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez",
              "Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin"]
        sid=1; idx=0
        classes=c.execute("SELECT class_id FROM classes ORDER BY class_id").fetchall()
        for (cid,) in classes:
            for _ in range(PER_CLASS):
                name=f"{first[idx%len(first)]} {last[(idx*3)%len(last)]}"
                c.execute("INSERT INTO students(student_id,student_name,class_id) VALUES (?,?,?)",(sid,name,cid))
                sid+=1; idx+=1
        c.commit()
    
    # Default assignments per class
    defaults=[("Homework 1",100.0),("Quiz 1",50.0),("Unit Test 1",100.0)]
    for (cid,) in c.execute("SELECT class_id FROM classes").fetchall():
        for an,tp in defaults:
            c.execute("INSERT OR IGNORE INTO assignments(class_id,assignment_name,total_points) VALUES (?,?,?)",(cid,an,tp))
    c.commit()
    
    # Parent accounts: one parent per student (each parent sees only their child)
    for (sid,) in c.execute("SELECT student_id FROM students").fetchall():
        u=f"parent_{sid:03d}"; pw=h(f"Parent@{sid}")
        c.execute("INSERT OR IGNORE INTO parent_accounts(username,password_hash,student_id) VALUES (?,?,?)",(u,pw,sid))
    c.commit()

# Verify Authentication
# Checks teacher first, then parent login
def login(c,u,p):
    r=c.execute("SELECT password_hash FROM users WHERE username=?",(u,)).fetchone()
    if r and h(p)==r[0]: return ("teacher",None)
    r=c.execute("SELECT password_hash,student_id FROM parent_accounts WHERE username=?",(u,)).fetchone()
    if r and h(p)==r[0]: return ("parent",r[1])
    return None

# The Database Queries 
def classes(c): return c.execute("SELECT class_id,class_name FROM classes ORDER BY class_id").fetchall()
def students(c,cid): return c.execute("SELECT student_id,student_name FROM students WHERE class_id=? ORDER BY student_id",(cid,)).fetchall()
def assigns(c,cid): return c.execute("SELECT assignment_id,assignment_name,total_points FROM assignments WHERE class_id=? ORDER BY assignment_name",(cid,)).fetchall()
def sid_class(c,sid):
    r=c.execute("SELECT class_id FROM students WHERE student_id=?",(sid,)).fetchone()
    return r[0] if r else None

# Calculates current grade % for a student in their class (earned / possible)
def grade_pct(c,sid):
    cid=sid_class(c,sid)
    if cid is None: return None
    total=float(c.execute("SELECT COALESCE(SUM(total_points),0) FROM assignments WHERE class_id=?",(cid,)).fetchone()[0])
    if total==0: return 0.0
    earned=float(c.execute("""SELECT COALESCE(SUM(g.points_earned),0)
        FROM grades g JOIN assignments a ON a.assignment_id=g.assignment_id
        WHERE g.student_id=? AND a.class_id=?""",(sid,cid)).fetchone()[0])
    return round((earned/total)*100,2)

# Returns list of assignments missing (No grade recorded yet)
def missing(c,sid):
    cid=sid_class(c,sid)
    if cid is None: return []
    return [r[0] for r in c.execute("""
        SELECT a.assignment_name FROM assignments a
        WHERE a.class_id=? AND a.assignment_id NOT IN (SELECT assignment_id FROM grades WHERE student_id=?)
        ORDER BY a.assignment_name""",(cid,sid)).fetchall()]


# Inserts or updates a grade using on conflict
def record(c,sid,aid,pts):
    total=c.execute("SELECT total_points FROM assignments WHERE assignment_id=?",(aid,)).fetchone()
    if not total: raise ValueError("Assignment not found.")
    total=float(total[0])
    if pts<0 or pts>total: raise ValueError(f"Points must be between 0 and {total}.")
    c.execute("""INSERT INTO grades(student_id,assignment_id,points_earned) VALUES (?,?,?)
        ON CONFLICT(student_id,assignment_id) DO UPDATE SET points_earned=excluded.points_earned""",(sid,aid,pts))
    c.commit()

# Assignment Manager
def add_a(c,cid,name,total):
    # Adds new asignments
    name=name.strip()
    if not name: raise ValueError("Name required.")
    if total<=0: raise ValueError("Total must be > 0.")
    c.execute("INSERT INTO assignments(class_id,assignment_name,total_points) VALUES (?,?,?)",(cid,name,total)); c.commit()

def upd_a(c,aid,name,total):
    # Modifies new or current asignments
    name=name.strip()
    if not name: raise ValueError("Name required.")
    if total<=0: raise ValueError("Total must be > 0.")
    cid=c.execute("SELECT class_id FROM assignments WHERE assignment_id=?",(aid,)).fetchone()
    if not cid: raise ValueError("Assignment not found.")
    cid=cid[0]
    ex=c.execute("SELECT assignment_id FROM assignments WHERE class_id=? AND assignment_name=?",(cid,name)).fetchone()
    if ex and ex[0]!=aid: raise ValueError("Duplicate name in this class.")
    c.execute("UPDATE assignments SET assignment_name=?, total_points=? WHERE assignment_id=?",(name,total,aid)); c.commit()

def del_a(c,aid):
    # Deletes an assignment and also deletes related grade rows due to on delete cascade
    c.execute("DELETE FROM assignments WHERE assignment_id=?",(aid,)); c.commit()

# GUI Helper: Table with Scrollbar
def tree_with_scroll(parent, cols, widths=None, height=18):
    wrap=ttk.Frame(parent); wrap.pack(fill="both",expand=True,padx=6,pady=6)
    t=ttk.Treeview(wrap, columns=cols, show="headings", height=height)
    sb=ttk.Scrollbar(wrap, orient="vertical", command=t.yview); t.configure(yscrollcommand=sb.set)
    t.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
    for c in cols:
        t.heading(c,text=c); t.column(c,width=(widths.get(c,160) if widths else 160))
    return t

# ------------------------------------------------------------
# Tkinter GUI Application
# ------------------------------------------------------------
# Screens:
# - Login Screen (Teacher or Parent)
# - Teacher Dashboard (class list)
# - Class Manager tabs:
#   1) Roster + submission tracking + search
#   2) Record grades
#   3) Progress report (GUI)
#   4) Struggling students (threshold)
#   5) Assignment manager (add/edit/delete)
# - Parent Portal (read-only: only for their child)
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP); self.geometry("1100x700")
        # Start DB connection and set up tables/data
        self.c=conn(); init(self.c); seed(self.c)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.show_login()

    def close(self):
        # Safely close DB when window exits
        try: self.c.close()
        except: pass
        self.destroy()

    def clear(self):
        for w in self.winfo_children(): w.destroy()

    def header(self, left, back=None):
        top=ttk.Frame(self,padding=10); top.pack(fill="x")
        ttk.Label(top,text=left,font=("Segoe UI",16,"bold")).pack(side="left")
        ttk.Button(top,text="Logout",command=self.show_login).pack(side="right")
        if back: ttk.Button(top,text="Back",command=back).pack(side="right",padx=6)

    # Login Screen
    def show_login(self):
        self.clear()
        f=ttk.Frame(self,padding=20); f.pack(fill="both",expand=True)
        ttk.Label(f,text=APP,font=("Segoe UI",20,"bold")).pack(pady=(0,10))
        ttk.Label(f,text="Login",font=("Segoe UI",14)).pack(pady=(0,15))
        form=ttk.Frame(f); form.pack()
        ttk.Label(form,text="Username:").grid(row=0,column=0,sticky="e",padx=8,pady=6)
        ttk.Label(form,text="Password:").grid(row=1,column=0,sticky="e",padx=8,pady=6)
        u=ttk.Entry(form,width=30); p=ttk.Entry(form,width=30,show="*")
        u.grid(row=0,column=1,pady=6); p.grid(row=1,column=1,pady=6)
        ttk.Label(f,text="Parent: parent_### / Parent@<id>\nExample: parent_001 / Parent@1").pack(pady=12)

        def go():
            res=login(self.c,u.get().strip(),p.get().strip())
            if not res: return messagebox.showerror("Login Failed","Invalid username or password.")
            role,sid=res
            self.teacher_home() if role=="teacher" else self.parent_view(sid)

        ttk.Button(f,text="Login",command=go).pack(pady=10)

    # Teacher Dashboard
    def teacher_home(self):
        self.clear(); self.header(APP)
        body=ttk.Frame(self,padding=10); body.pack(fill="both",expand=True)
        left=ttk.Frame(body); left.pack(side="left",fill="y",padx=(0,10))
        ttk.Label(left,text="Ms. Carter's Classes",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=(0,6))
        lb=tk.Listbox(left,height=10,width=35); lb.pack(fill="y")
        for cid,name in classes(self.c): lb.insert("end",f"{cid}. {name}")

        def open_class():
            sel=lb.curselection()
            if not sel: return messagebox.showinfo("Select Class","Please select a class.")
            cid=int(lb.get(sel[0]).split(".")[0]); self.class_mgr(cid)

        ttk.Button(left,text="Open Class",command=open_class).pack(pady=10,fill="x")

        right=ttk.Frame(body); right.pack(side="left",fill="both",expand=True)
        ttk.Label(right,text="Features:",font=("Segoe UI",12,"bold")).pack(anchor="w")
        ttk.Label(right,text="- Search by name/ID\n- Progress report + missing work\n- Struggling students\n- Assignment manager (CRUD)\n- Parent read-only login").pack(anchor="w",pady=6)

    # Class Manager (The Tabs)
    def class_mgr(self, cid):
        self.clear()
        cname=self.c.execute("SELECT class_name FROM classes WHERE class_id=?",(cid,)).fetchone()[0]
        self.header(f"{APP} | {cname}", back=self.teacher_home)

        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=10,pady=10)
        t1,t2,t3,t4,t5=[ttk.Frame(nb) for _ in range(5)]
        nb.add(t1,text="Roster & Submissions"); nb.add(t2,text="Record Grades")
        nb.add(t3,text="Progress Report"); nb.add(t4,text="Struggling"); nb.add(t5,text="Assignments")

        self.tab_roster(t1,cid); self.tab_record(t2,cid); self.tab_report(t3,cid); self.tab_struggle(t4,cid); self.tab_assign(t5,cid)

    def tab_roster(self, parent, cid):
        ttk.Label(parent,text="Roster + Submission Tracking",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=6)
        sf=ttk.Frame(parent,padding=6); sf.pack(fill="x")
        ttk.Label(sf,text="Search (ID or Name):").pack(side="left")
        q=tk.StringVar(); e=ttk.Entry(sf,textvariable=q,width=30); e.pack(side="left",padx=8)
        ttk.Button(sf,text="Clear",command=lambda:q.set("")).pack(side="left")

        cols=("Student ID","Student Name","Grade %","Missing #")
        tree=tree_with_scroll(parent,cols,widths={"Student ID":110,"Student Name":340,"Grade %":130,"Missing #":130})

        def refresh():
            tree.delete(*tree.get_children())
            s=students(self.c,cid); term=q.get().strip().lower()
            for sid,name in s:
                if term and term not in str(sid) and term not in name.lower(): continue
                g=grade_pct(self.c,sid) or 0.0
                tree.insert("", "end", values=(sid,name,f"{g:.2f}",len(missing(self.c,sid))))

        ttk.Button(parent,text="Refresh",command=refresh).pack(anchor="e",padx=6,pady=(0,8))
        e.bind("<KeyRelease>",lambda _ : refresh()); refresh()

    def tab_report(self, parent, cid):
        ttk.Label(parent,text="Progress Report",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=6)
        sf=ttk.Frame(parent,padding=6); sf.pack(fill="x")
        ttk.Label(sf,text="Search (ID or Name):").pack(side="left")
        q=tk.StringVar(); e=ttk.Entry(sf,textvariable=q,width=30); e.pack(side="left",padx=8)
        ttk.Button(sf,text="Clear",command=lambda:q.set("")).pack(side="left")

        cols=("Student ID","Student Name","Grade %","Missing Assignments")
        tree=tree_with_scroll(parent,cols,widths={"Student ID":110,"Student Name":340,"Grade %":130,"Missing Assignments":420})

        def refresh():
            tree.delete(*tree.get_children())
            term=q.get().strip().lower()
            for sid,name in students(self.c,cid):
                if term and term not in str(sid) and term not in name.lower(): continue
                g=grade_pct(self.c,sid) or 0.0
                miss=missing(self.c,sid)
                tree.insert("", "end", values=(sid,name,f"{g:.2f}",(", ".join(miss) if miss else "None")))

        ttk.Button(parent,text="Refresh",command=refresh).pack(anchor="e",padx=6,pady=(0,8))
        e.bind("<KeyRelease>",lambda _ : refresh()); refresh()

    def tab_struggle(self, parent, cid):
        ttk.Label(parent,text="Struggling Students",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=6)
        top=ttk.Frame(parent,padding=8); top.pack(fill="x")
        ttk.Label(top,text="Threshold (%):").pack(side="left")
        th=tk.StringVar(value="70"); ttk.Entry(top,textvariable=th,width=8).pack(side="left",padx=8)

        cols=("Student ID","Student Name","Grade %","Missing #")
        tree=tree_with_scroll(parent,cols,widths={"Student ID":110,"Student Name":340,"Grade %":130,"Missing #":130})

        def refresh():
            tree.delete(*tree.get_children())
            t=fnum(th.get())
            if t is None: return messagebox.showerror("Error","Threshold must be a number.")
            for sid,name in students(self.c,cid):
                g=grade_pct(self.c,sid) or 0.0
                if g < t:
                    tree.insert("", "end", values=(sid,name,f"{g:.2f}",len(missing(self.c,sid))))

        ttk.Button(top,text="Refresh",command=refresh).pack(side="left",padx=10)
        refresh()

    def tab_record(self, parent, cid):
        ttk.Label(parent,text="Record Grades",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=6)
        form=ttk.Frame(parent,padding=8); form.pack(fill="x")
        ttk.Label(form,text="Student:").grid(row=0,column=0,sticky="e",padx=6,pady=6)
        ttk.Label(form,text="Assignment:").grid(row=1,column=0,sticky="e",padx=6,pady=6)
        ttk.Label(form,text="Points Earned:").grid(row=2,column=0,sticky="e",padx=6,pady=6)

        sv,av,pv=tk.StringVar(),tk.StringVar(),tk.StringVar()
        sbox=ttk.Combobox(form,textvariable=sv,state="readonly",width=45,
            values=[f"{sid} - {name}" for sid,name in students(self.c,cid)])
        abox=ttk.Combobox(form,textvariable=av,state="readonly",width=45)
        pts=ttk.Entry(form,textvariable=pv,width=20)
        sbox.grid(row=0,column=1,sticky="w",padx=6,pady=6)
        abox.grid(row=1,column=1,sticky="w",padx=6,pady=6)
        pts.grid(row=2,column=1,sticky="w",padx=6,pady=6)

        def load_a():
            a=assigns(self.c,cid)
            abox["values"]=[f"{aid} - {n} (/{t})" for aid,n,t in a]
            av.set(abox["values"][0] if abox["values"] else "")

        def save():
            if not sv.get() or not av.get(): return messagebox.showinfo("Missing","Select student and assignment.")
            ptsv=fnum(pv.get())
            if ptsv is None: return messagebox.showerror("Error","Points must be a number.")
            try:
                sid=int(sv.get().split(" - ")[0]); aid=int(av.get().split(" - ")[0])
                record(self.c,sid,aid,ptsv)
                messagebox.showinfo("Saved","Grade recorded.")
            except Exception as e:
                messagebox.showerror("Error",str(e))

        ttk.Button(form,text="Save Grade",command=save).grid(row=3,column=1,sticky="w",padx=6,pady=10)
        ttk.Button(form,text="Reload Assignments",command=load_a).grid(row=3,column=1,sticky="e",padx=6,pady=10)
        load_a()

    def tab_assign(self, parent, cid):
        ttk.Label(parent,text="Assignment Manager (Add/Edit/Delete)",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=6)
        cols=("ID","Name","Total")
        tree=tree_with_scroll(parent,cols,widths={"ID":90,"Name":420,"Total":120},height=16)

        ctrl=ttk.Frame(parent,padding=8); ctrl.pack(fill="x")
        nv,tv=tk.StringVar(),tk.StringVar()
        ttk.Label(ctrl,text="Name:").grid(row=0,column=0,sticky="e",padx=6,pady=6)
        ttk.Entry(ctrl,textvariable=nv,width=40).grid(row=0,column=1,sticky="w",padx=6,pady=6)
        ttk.Label(ctrl,text="Total:").grid(row=0,column=2,sticky="e",padx=6,pady=6)
        ttk.Entry(ctrl,textvariable=tv,width=12).grid(row=0,column=3,sticky="w",padx=6,pady=6)

        def refresh():
            tree.delete(*tree.get_children())
            for aid,n,t in assigns(self.c,cid):
                tree.insert("", "end", values=(aid,n,t))

        def pick(_=None):
            sel=tree.selection()
            if not sel: return
            aid,n,t=tree.item(sel[0],"values")
            nv.set(n); tv.set(str(t))

        tree.bind("<<TreeviewSelect>>", pick)

        def add():
            tot=fnum(tv.get())
            if tot is None: return messagebox.showerror("Error","Total must be a number.")
            try:
                add_a(self.c,cid,nv.get(),tot)
                refresh(); nv.set(""); tv.set("")
            except Exception as e:
                messagebox.showerror("Error",str(e))

        def edit():
            sel=tree.selection()
            if not sel: return messagebox.showinfo("Select","Select an assignment.")
            aid=int(tree.item(sel[0],"values")[0])
            tot=fnum(tv.get())
            if tot is None: return messagebox.showerror("Error","Total must be a number.")
            try:
                upd_a(self.c,aid,nv.get(),tot)
                refresh()
            except Exception as e:
                messagebox.showerror("Error",str(e))

        def delete():
            sel=tree.selection()
            if not sel: return messagebox.showinfo("Select","Select an assignment.")
            aid=int(tree.item(sel[0],"values")[0])
            name=tree.item(sel[0],"values")[1]
            if not messagebox.askyesno("Confirm",f"Delete '{name}' and its grades?"): return
            del_a(self.c,aid); refresh(); nv.set(""); tv.set("")

        btns = ttk.Frame(ctrl)
        btns.grid(row=1, column=0, columnspan=4, pady=10)

        ttk.Button(btns, text="Add Assignment", width=18, command=add).pack(side="left", padx=6)
        ttk.Button(btns, text="Edit Assignment", width=18, command=edit).pack(side="left", padx=6)
        ttk.Button(btns, text="Delete Assignment", width=18, command=delete).pack(side="left", padx=6)
        ttk.Button(btns, text="Refresh List", width=18, command=refresh).pack(side="left", padx=6)

        refresh()

    def parent_view(self, sid):
        self.clear(); self.header(f"{APP} | Parent Portal")
        row=self.c.execute("SELECT student_name FROM students WHERE student_id=?",(sid,)).fetchone()
        if not row: return messagebox.showerror("Error","Student not found.")
        name=row[0]
        g=grade_pct(self.c,sid) or 0.0
        miss=missing(self.c,sid)

        s=ttk.Frame(self,padding=10); s.pack(fill="x")
        ttk.Label(s,text=f"Student: {name} (ID: {sid})",font=("Segoe UI",12,"bold")).pack(anchor="w")
        ttk.Label(s,text=f"Current Grade: {g:.2f}%").pack(anchor="w")
        ttk.Label(s,text="Missing: "+(", ".join(miss) if miss else "None")).pack(anchor="w")

        cols=("Assignment","Total","Earned")
        tree=tree_with_scroll(self,cols,widths={"Assignment":420,"Total":140,"Earned":180})
        tree.delete(*tree.get_children())
        cid=sid_class(self.c,sid)
        for an,tp,earned in self.c.execute("""
            SELECT a.assignment_name,a.total_points,
            (SELECT g.points_earned FROM grades g WHERE g.student_id=? AND g.assignment_id=a.assignment_id)
            FROM assignments a WHERE a.class_id=? ORDER BY a.assignment_name""",(sid,cid)).fetchall():
            tree.insert("", "end", values=(an,tp,(earned if earned is not None else "Not Submitted")))

if __name__=="__main__":
    App().mainloop()