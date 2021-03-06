"""A Ttk Notebook with close buttons.

Based on an example by patthoyts, http://paste.tclers.tk/896
"""
import os
import Tkinter as tk
import ttk
import os.path
from tkFileDialog import *
import tkMessageBox
import tkSimpleDialog

#http://effbot.org/tkbook/menu.htm

class Analysis:

    def __init__(self, fileName):
        self.fileName = fileName
        self.s1 = "text1"
        self.s2 = "text2"

    def save(self):
        print "save"

class Preferences:

    def __init__(self):
        self.workSpaceFolder = ""

    def addRecent(self, path):
        pass
        
class Recent:

    def __init__(self, file):
        self.file = file

    def __call__(self):
        pass

class ConfirmClose(tkSimpleDialog.Dialog):

    def __init__(self, parent, name):

        self.name = name

        self.close = False
        self.save = False

        imgdir = os.path.join(os.path.dirname(__file__), 'img')

        self.img_logo = tk.PhotoImage("img_logo", file=os.path.join(imgdir, 'logo.gif'))

        tkSimpleDialog.Dialog.__init__(self, parent, "Confirm File Close")

    def body(self, master):

        tk.Label(master, image = self.img_logo).grid(column=0, row=0)
        tk.Label(master, text="Do you want to save the changes you made to {0}?".format(self.name)).grid(column=1, row=0)

    def buttonbox(self):
        
        try:
            self.attributes("-toolwindow",1) #only works on windows
        except:
            #self.overrideredirect(1) #removes whole frame
            self.resizable(0,0) #stops maximising and resizing but can still be minimised

        box = tk.Frame(self)

        w = tk.Button(box, text="Don't Save", width=10, command=self.close_dont_save)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        
        w = tk.Button(box, text="Cancel", width=10, command=self.cancel)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        
        w = tk.Button(box, text="Save", width=10, command=self.close_and_save, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Return>", self.close_and_save)
        self.bind("<Escape>", self.cancel)

        box.pack()

    def close_dont_save(self, event=None):
        self.close = True
        self.save = False
        self.close_window()

    def close_and_save(self, event=None):
        self.close = True
        self.save = True
        self.close_window()

    def cancel(self, event=None):
        self.close = False
        self.save = False
        self.close_window()

    def close_window(self):
        self.parent.focus_set()
        self.destroy()

class FileOpener:

    def __init__(self, root, tabs, preferences):
        self.root = root
        self.tabs = tabs
        self.preferences = preferences

    def openFile(self):

        fileName = self.SelectFile(parent=self.root, defaultextension=".xml")

        if len(fileName) > 0:
            self.tabs.addAnalysis(fileName)
            self.preferences.addRecent(fileName)

    def SelectFile(self, parent, defaultextension=None):
            if len(preferences.workSpaceFolder) > 0:
                    return askopenfilename(parent=parent, initialdir=preferences.workSpaceFolder, defaultextension=defaultextension)
            else:
                    return askopenfilename(parent=parent, defaultextension=defaultextension)

def openMaximized(root):

    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry("%dx%d+0+0" % (w, h))

def getRecent():

    recent = []

    recent.append("One")
    recent.append("Two")
    recent.append("Three")
    recent.append("Four")

    return recent

def addRecent(recent_menu):

    for recent in getRecent():
        recent_menu.add_command(label=recent, command = Recent(recent))
        
def hello():
    print "hello!"

def getTabID(notebook):
    my_tabs = notebook.tabs()
    tab_id = my_tabs[len(my_tabs) - 1]
    return tab_id

class ClosableTab:

    def __init__(self, notebook, fileName, console):

        self.console = console
        self.name = os.path.basename(fileName)
        self.frame = tk.Frame(notebook)

        notebook.add(self.frame, text=self.name, padding=3)
        self.index = self.getTabIndex(notebook)

    def close(self):

        d = ConfirmClose(root, self.name)

        if d.save:
            self.save()
            self.console.write("{0} saved".format(self.name))

        return d.close

    def getTabIndex(self, notebook):
        my_tabs = notebook.tabs()
        return len(my_tabs) - 1

    def save(self):
        pass

class AnalysisTab(ClosableTab):

    def __init__(self, notebook, fileName, console):

        ClosableTab.__init__(self, notebook, fileName, console)

        self.analysis = Analysis(fileName)

        sub_tabs = ValidationTabs(self.frame)

        main_frame = sub_tabs.add("Main Settings")
        correction_frame = sub_tabs.add("Correction Settings")

        s1Var = tk.StringVar()
        s2Var = tk.StringVar()
        s1Var.set(self.analysis.s1)
        s2Var.set(self.analysis.s2)
        square1Label = tk.Label(main_frame.frame,textvariable=s1Var)
        square1Label.grid(row=0, column=7)
        square2Label = tk.Label(main_frame.frame,textvariable=s2Var)
        square2Label.grid(row=0, column=6)

        sub_tabs.pack()

        main_frame.validate(False)

        notebook.pack(expand=1, fill='both')

    def save(self):
        self.analysis.save()

class ClosableTabs:

    def __init__(self, parent, console):

        self.console = console
        self.loadImages()

        self.style = self.createClosableTabStyle()

        parent.bind_class("TNotebook", "<ButtonPress-1>", self.btn_press, True)
        parent.bind_class("TNotebook", "<ButtonRelease-1>", self.btn_release)

        #add notebook (holds tabs)
        self.nb = ttk.Notebook(parent, style="ButtonNotebook")
        self.nb.pressed_index = None

        self.tabs = {}

    def addAnalysis(self, fileName):

        closableTab = AnalysisTab(self.nb, fileName, self.console)

        self.tabs[closableTab.index] = closableTab

        return closableTab

    def loadImages(self):

        imgdir = os.path.join(os.path.dirname(__file__), 'img')

        self.i1 = tk.PhotoImage("img_close", file=os.path.join(imgdir, 'close.gif'))
        self.i2 = tk.PhotoImage("img_closeactive",
            file=os.path.join(imgdir, 'close_active.gif'))
        self.i3 = tk.PhotoImage("img_closepressed",
            file=os.path.join(imgdir, 'close_pressed.gif'))

    def btn_press(self, event):

        x, y, widget = event.x, event.y, event.widget
        elem = widget.identify(x, y)

        try:

            index = widget.index("@%d,%d" % (x, y))

            if "close" in elem:
                widget.state(['pressed'])
                widget.pressed_index = index
        
        except:

            pass

    def close_tab(self, widget, index):

        tab = self.tabs[index]

        if tab.close():
            widget.forget(index)
            widget.event_generate("<<NotebookClosedTab>>")

    def btn_release(self, event):
        x, y, widget = event.x, event.y, event.widget

        if not widget.instate(['pressed']):
            return

        elem =  widget.identify(x, y)
        index = widget.index("@%d,%d" % (x, y))

        if "close" in elem and widget.pressed_index == index:
            self.close_tab(widget, index)

        widget.state(["!pressed"])
        widget.pressed_index = None

    def createClosableTabStyle(self):

        style = ttk.Style()

        style.element_create("close", "image", "img_close",
            ("active", "pressed", "!disabled", "img_closepressed"),
            ("active", "!disabled", "img_closeactive"), border=8, sticky='')

        style.layout("ButtonNotebook", [("ButtonNotebook.client", {"sticky": "nswe"})])
        style.layout("ButtonNotebook.Tab", [
            ("ButtonNotebook.tab", {"sticky": "nswe", "children":
                [("ButtonNotebook.padding", {"side": "top", "sticky": "nswe",
                                             "children":
                    [("ButtonNotebook.focus", {"side": "top", "sticky": "nswe",
                                               "children":
                        [("ButtonNotebook.label", {"side": "left", "sticky": ''}),
                         ("ButtonNotebook.close", {"side": "left", "sticky": ''})]
                    })]
                })]
            })]
        )

        return style

class ValidationTabs:

    def __init__(self, parent):

        self.loadImages()

        #add notebook (holds tabs)
        self.nb = ttk.Notebook(parent)
        self.nb.pressed_index = None

    def add(self, name):

        my_frame = tk.Frame(self.nb)
        self.nb.add(my_frame, text=name, padding=3)

        tab_id = getTabID(self.nb)

        validationTab = ValidationTab(self.nb, tab_id, my_frame, self.img_invalid)

        return validationTab

    def loadImages(self):

        imgdir = os.path.join(os.path.dirname(__file__), 'img')

        self.img_valid = tk.PhotoImage("img_valid", file=os.path.join(imgdir, 'valid.gif'))
        self.img_invalid = tk.PhotoImage("img_invalid", file=os.path.join(imgdir, 'invalid.gif'))

    def pack(self):

        self.nb.pack(expand=1, fill='both')

class ValidationTab:

    def __init__(self, notebook, tab_id, frame, img_invalid):

        self.notebook = notebook
        self.tab_id = tab_id
        self.frame = frame
        self.img_invalid = img_invalid

    def validate(self, valid):
        
        if not valid:
            self.notebook.tab(self.tab_id, image = self.img_invalid, compound=tk.RIGHT)
        else:
            self.notebook.tab(self.tab_id, image = None)

class Console:

    def __init__(self, parent):

        scrollbar = tk.Scrollbar(parent, orient=tk.VERTICAL)
        self.listbox = tk.Listbox(parent, yscrollcommand=scrollbar.set, selectmode=tk.EXTENDED)
        scrollbar.configure(command=self.listbox.yview)

        self.listbox.pack(side=tk.LEFT,fill=tk.BOTH, expand=1, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

    def write(self, line):

        self.listbox.insert(tk.END, str(line))

class PCWG:

    def __init__(self, root):

        self.root = root
        
        tab_frame = tk.Frame(root)
        console_frame = tk.Frame(root, background="grey")
        
        tab_frame.grid(row=0, column=0, sticky="nsew")
        console_frame.grid(row=1, column=0, sticky="nsew")
        
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        
        console = Console(console_frame)
        tabs = ClosableTabs(tab_frame, console)

        self.preferences = Preferences()
        self.fileOpener = FileOpener(root, tabs, self.preferences)

        self.addMenus(root)

    def addMenus(self, root):

        #add menu
        self.menubar = tk.Menu(root)

        # create a pulldown menu, and add it to the menu bar
        filemenu = tk.Menu(self.menubar)

        new_menu = tk.Menu(self.menubar)
        new_menu.add_command(label="Analysis")
        new_menu.add_command(label="Dataset")
        new_menu.add_command(label="Portfolio")

        self.menubar.add_cascade(label="File", menu=filemenu)
        filemenu.add_cascade(label="New", menu=new_menu)

        filemenu.add_command(label="Open", command=self.fileOpener.openFile)

        recent_menu = tk.Menu(self.menubar)
        addRecent(recent_menu)
        filemenu.add_cascade(label="Open Recent", menu=recent_menu)

        filemenu.add_command(label="Save")
        filemenu.add_command(label="Save As")
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=root.quit)

        #analysis_menu.add_command(label="Analysis")
        #filemenu.add_command(label="Dataset")
        #filemenu.add_command(label="Portfolio")
        #filemenu.add_cascade(label="Analysis", menu=filemenu)

        # create more pulldown menus
        editmenu = tk.Menu(self.menubar, tearoff=0)
        editmenu.add_command(label="Cut", command=hello)
        editmenu.add_command(label="Copy", command=hello)
        editmenu.add_command(label="Paste", command=hello)
        self.menubar.add_cascade(label="Edit", menu=editmenu)

        helpmenu = tk.Menu(self.menubar, tearoff=0)
        helpmenu.add_command(label="About", command=hello)
        self.menubar.add_cascade(label="Help", menu=helpmenu)

        # display the menu
        root.config(menu=self.menubar)

#start of main code

root = tk.Tk()

menu = PCWG(root)

openMaximized(root)

root.mainloop()