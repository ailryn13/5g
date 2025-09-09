#!/usr/bin/env python3
import gi, os, signal
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gtk, Gdk, Vte, GLib

PLAY_SYMBOL = "\u25B6"  # ▶
STOP_SYMBOL = "\u25A0"   # ■

class SimulationTestBedApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="5G Simulation Test Bed")
        self.set_default_size(1000, 700)
        self.setup_css()
        self.terminals = {}

        # Runtime control state
        self.gnb_running = False
        self.gnb_terminal_ref = None
        self.gnb_button_ref = None
        self.ue_running = False
        self.ue_terminal_ref = None
        self.ue_button_ref = None
        self.is_terminal_position_set = False

        # Main layout
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(self.paned)

        # Sidebar
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main_menu_items = ["Network Overview", "5G Core Network", "gNB", "User Equipment"]
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        for title in self.main_menu_items:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=title, xalign=0)
            label.get_style_context().add_class("big-menu-label")
            row.add(label)
            self.listbox.add(row)
        self.listbox.connect("row-selected", self.on_menu_selected)
        sidebar.pack_start(self.listbox, True, True, 0)
 
        sidebar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, True, 8)
        self.license_btn = Gtk.Button(label="License")
        self.license_btn.get_style_context().add_class("big-menu-label")
        self.license_btn.connect("clicked", self.on_license_selected)
        sidebar.pack_end(self.license_btn, False, False, 10)
        self.paned.pack1(sidebar, resize=False, shrink=False)

        # Right content area is now the top of a vertical pane
        self.content_paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.content_paned.connect("size-allocate", self.on_content_paned_allocated)
        self.paned.pack2(self.content_paned, resize=True, shrink=False)

        # The original content_box widget is placed in the top part of the pane
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.content_paned.pack1(self.content_box, resize=True, shrink=False)

        # Terminal notebook is placed in the bottom part of the pane
        self.terminal_notebook = Gtk.Notebook()
        self.terminal_notebook.set_scrollable(True)
        self.terminal_notebook.hide()
        self.content_paned.pack2(self.terminal_notebook, resize=True, shrink=False)

        self.paned.set_position(300)
        # Select "Network Overview" by default on startup
        self.listbox.select_row(self.listbox.get_row_at_index(0))
        self.show_all()

    def on_content_paned_allocated(self, widget, allocation):
        # This function runs whenever the container is resized.
        # It sets the default position only once when the terminal becomes visible.
        if not self.is_terminal_position_set and self.terminal_notebook.is_visible() and allocation.height > 0:
            
            # This is the number you can change for the terminal height
            widget.set_position(260)
            
            # Set the flag to True so this code only ever runs ONCE.
            self.is_terminal_position_set = True

    def setup_css(self):
        css = b"""
        .big-menu-label { font-size: 16px; padding: 8px; }
        .header-title { font-weight: bold; font-size: 18px; margin-bottom: 5px; }
        .content-box { border-radius: 6px; padding: 10px; }
        .start-button { background: #2ecc71; color: white; font-weight: bold; }
        .stop-button { background: #e74c3c; color: white; font-weight: bold; }
        .active-submenu { background: orange; color: white; font-weight: bold; }
        """
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_menu_selected(self, listbox, row):
        if row:
            section = self.main_menu_items[row.get_index()]
            for child in self.content_box.get_children():
                if child != self.terminal_notebook:
                    self.content_box.remove(child)

            if section == "Network Overview":
                self.show_network_overview()
            elif section == "5G Core Network":
                self.show_core_menu()
            elif section == "gNB":
                self.show_gnb_menu()
            elif section == "User Equipment":
                self.show_ue_menu()
            self.content_box.show_all()

    def on_license_selected(self, _):
        self.listbox.unselect_all()
        for child in self.content_box.get_children():
            if child != self.terminal_notebook:
                self.content_box.remove(child)
        lbl = Gtk.Label(label="License information goes here.")
        lbl.set_valign(Gtk.Align.START)
        self.content_box.pack_start(lbl, True, True, 10)
        self.terminal_notebook.hide()
        self.content_box.show_all()

    def make_submenu_click_handler(self, button_list, clicked_button, callback):
        def handler(_):
            for b in button_list:
                b.get_style_context().remove_class("active-submenu")
            clicked_button.get_style_context().add_class("active-submenu")
            callback(None)
        return handler

    def add_toolbar_with_content(self, items, content_attr, button_list_attr):
        vbox_main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        hbox_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hbox_buttons.set_margin_top(15)
        hbox_buttons.set_margin_start(15)

        btn_list = []
        for title, handler in items:
            btn = Gtk.Button(label=title)
            btn.set_size_request(150, 40)
            btn.get_style_context().add_class("big-menu-label")
            btn.connect("clicked", self.make_submenu_click_handler(btn_list, btn, handler))
            btn_list.append(btn)
            hbox_buttons.pack_start(btn, False, False, 0)

        setattr(self, button_list_attr, btn_list)
        vbox_main.pack_start(hbox_buttons, False, False, 0)

        setattr(self, content_attr, Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10))
        getattr(self, content_attr).set_margin_start(15)
        getattr(self, content_attr).set_margin_top(10)
        vbox_main.pack_start(getattr(self, content_attr), True, True, 0)
        self.content_box.pack_start(vbox_main, True, True, 0)

    def create_cli_view(self, parent_box, commands_list):
        # 1. Clear the parent container of any previous widgets
        for c in parent_box.get_children(): parent_box.remove(c)

        # 2. Create the main resizable container (top for buttons, bottom for terminal)
        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        parent_box.pack_start(paned, True, True, 0)

        # 3. Create the top part for the command buttons
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        button_box.set_margin_top(10)
        button_box.set_margin_bottom(10)
        button_box.set_margin_start(10)
        button_box.set_margin_end(10)
        scrolled_window.add(button_box)
        paned.pack1(scrolled_window, resize=True, shrink=False)

        # 4. Create the bottom part for the terminal
        terminal = Vte.Terminal()
        terminal.spawn_async(Vte.PtyFlags.DEFAULT, os.environ['HOME'], ["/bin/bash"], [], GLib.SpawnFlags.DEFAULT, None, None, -1, None, None)
        paned.pack2(terminal, resize=True, shrink=True)

        # 5. Define a handler and create buttons for the commands
        def on_command_button_clicked(button, command):
            # Add a newline to execute the command and feed it to the terminal
            terminal.feed_child((command + "\n").encode())

        for cmd in commands_list:
            btn = Gtk.Button(label=cmd)
            btn.set_halign(Gtk.Align.START)
            btn.connect("clicked", on_command_button_clicked, cmd)
            button_box.pack_start(btn, False, False, 0)
        
        # 6. Show all the new widgets and set a default size for the panes
        parent_box.show_all()
        GLib.idle_add(paned.set_position, 250) # Sets the button area height to 250px

    def show_network_overview(self):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        hbox.set_homogeneous(True)
        hbox.pack_start(self.create_box_with_ue_control("UE"), True, True, 0)
        hbox.pack_start(self.create_box_with_gnb_control("gNB"), True, True, 0)
        hbox.pack_start(self.create_box_with_start("5G Core", self.start_5g_terminal, "Show Daemons"), True, True, 0)
        self.content_box.pack_start(hbox, False, False, 15)

    def show_core_menu(self):
        items = [
            ("Service Daemons", self.on_core_daemons),
            ("Binaries", self.on_core_binaries),
            ("Configuration", self.on_core_config),
            ("Logs", self.on_core_logs),
            ("Resource Monitor", self.on_core_monitor)
        ]
        self.add_toolbar_with_content(items, "core_area", "core_buttons")

    def show_gnb_menu(self):
        items = [("Binaries", self.on_gnb_binaries), ("Configuration", self.on_gnb_config), ("Logs", self.on_gnb_logs), ("CLI", self.on_gnb_cli)]
        self.add_toolbar_with_content(items, "gnb_area", "gnb_buttons")

    def show_ue_menu(self):
        items = [("Binaries", self.on_ue_binaries), ("Configuration", self.on_ue_config), ("Logs", self.on_ue_logs), ("CLI", self.on_ue_cli)]
        self.add_toolbar_with_content(items, "ue_area", "ue_buttons")

    def on_core_daemons(self, _):
        terminal = self.create_terminal_tab("5g_daemons", "5G Daemon Status")
        command = 'systemctl status open5gs-*\n'
        GLib.timeout_add(300, lambda: terminal.feed_child(command.encode()) or False)

    def on_core_binaries(self, _):
        terminal = self.create_terminal_tab("core_bin", "Core Binaries")
        command = 'find /usr/bin -type f -executable -name "open5gs-*"\n'
        GLib.timeout_add(300, lambda: terminal.feed_child(command.encode()) or False)

    def on_core_config(self, _):
        config_dir = "/etc/open5gs"
        if os.path.exists(config_dir):
            files = sorted([f for f in os.listdir(config_dir) if f.endswith('.yaml')])
        else:
            files = []
        
        box = self.core_area
        for child in box.get_children(): box.remove(child)

        listbox = Gtk.ListBox()
        for f in files:
            row = Gtk.ListBoxRow()
            btn = Gtk.Button(label=f, xalign=0)
            btn.connect("clicked", self.on_config_file_clicked, f)
            row.add(btn)
            listbox.add(row)
        
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(listbox)
        box.pack_start(scrolled_window, True, True, 15)
        box.show_all()

    def on_core_logs(self, _):
        log_dir = "/var/log/open5gs"
        if os.path.exists(log_dir):
            files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')])
        else:
            files = []
    
        box = self.core_area
        for child in box.get_children(): box.remove(child)

        listbox = Gtk.ListBox()
        for f in files:
            row = Gtk.ListBoxRow()
            btn = Gtk.Button(label=f, xalign=0)
            btn.connect("clicked", self.on_log_file_clicked, f)
            row.add(btn)
            listbox.add(row)
        
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(listbox)
        box.pack_start(scrolled_window, True, True, 15)
        box.show_all()
        
    def on_config_file_clicked(self, button, filename):
        terminal = self.create_terminal_tab("config_file_display", "Config file: " + filename)
        full_path=f"/etc/open5gs/{filename}"
        command = f'cat {full_path}\n'
        GLib.timeout_add(300,lambda: terminal.feed_child(command.encode()) or False)
        
    def on_log_file_clicked(self, button, filename):
        terminal = self.create_terminal_tab("core_logs_display", "Core Log: " + filename)
        full_path = f"/var/log/open5gs/{filename}"
        command = f'cat {full_path}\n'
        GLib.timeout_add(300, lambda: terminal.feed_child(command.encode()) or False)

    def on_core_monitor(self, _):
        box = self.core_area
        for c in box.get_children(): box.remove(c)
        box.pack_start(Gtk.Label(label="[Core] Resource Monitor details here."), True, True, 0)
        box.show_all()

    def on_gnb_binaries(self, _):
        # Placeholder for gNB control UI (if different from Network Overview)
        box = self.gnb_area
        for c in box.get_children(): box.remove(c)
        box.pack_start(Gtk.Label(label="gNB Control panel appears on the main Network Overview page."), True, True, 0)
        box.show_all()
    
    def on_gnb_config(self, _):
        # Clear the gnb_area of any previous widgets, like the placeholder label
        box = self.gnb_area
        for c in box.get_children(): box.remove(c)
        box.show_all()

        # Create a new terminal tab for this process
        terminal = self.create_terminal_tab("gnb_config", "gNB Configuration")

        # --- IMPORTANT ---
        # Define the commands and file paths you need.
        # These are placeholders; you must replace them with your actual paths and commands.
        config_dir = os.path.expanduser("./nr-gnb -c ../config/open5gs-gnb.yaml")
        config_file = os.path.join(config_dir, "amf.yaml")

        # This list contains the commands that will be run one-by-one.
        commands = [
            f"echo '--- Setting up gNB configuration ---'",
            f"cd UERANSIM",
            f"cd build",
            f"ls",
            f"{config_dir}"
        ]

        # Send the commands to the terminal
        self.send_commands_sequentially(terminal, commands)

    def on_gnb_logs(self, _):
        log_dir = "/var/log/open5gs"
        if os.path.exists(log_dir):
            files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')])
        else:
            files = []
        
        box = self.core_area
        for child in box.get_children(): box.remove(child)

        listbox = Gtk.ListBox()
        for f in files:
            row = Gtk.ListBoxRow()
            btn = Gtk.Button(label=f, xalign=0)
            btn.connect("clicked", self.on_log_file_clicked, f)
            row.add(btn)
            listbox.add(row)
        
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(listbox)
        box.pack_start(scrolled_window, True, True, 15)
        box.show_all()

    def on_gnb_cli(self, _):
        """
        Builds the gNB CLI view with command buttons in the content area
        and a dedicated, reusable terminal in the bottom notebook.
        """
        # 1. Get the content area and clear any previous widgets
        box = self.gnb_area
        for child in box.get_children():
            box.remove(child)

        # --- KEY CHANGE FOR UNIFORMITY ---
        # 2. Create the terminal in the bottom notebook using our existing helper.
        # This ensures it looks and feels like all other terminals.
        # We give it a unique key 'gnb_cli' so it can be reused.
        cli_terminal = self.create_terminal_tab("gnb_cli", "gNB CLI")

        # --- CUSTOMIZE YOUR COMMANDS HERE (No changes here) ---
        gnb_commands = [
            ("info | Show some informations about the gNB", "info"),
            ("status | Show some status information about the gNB", "status"),
            ("amf-list | List all AMFs associated with the gNB", "ue-context 1"),
            ("amf-info | Show some status information about the given AMF", "amf-info"),
            ("ue-list | List all UEs associated with the gNB", "ue-list"),
            ("ue-count | Print the total number of UEs connected the this gNB","ue-count"),
            ("ue-release | Request a UE context release for the given UE","ue-release")
        ]

        # 3. Create a horizontal box for the command buttons
        buttons_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        # 4. Create a button for each command and connect it to the terminal tab
        for label, command in gnb_commands:
            btn = Gtk.Button()
            label_widget=Gtk.Label(label=label)
            label_widget.set_xalign(0)
            btn.add(label_widget)
            # The handler now points to the terminal in the bottom notebook
            btn.connect("clicked", self.on_gnb_cli_command_clicked, cli_terminal, command)
            buttons_vbox.pack_start(btn, False, False, 0)
        
        # --- NEW: CREATE A SCROLLED WINDOW ---
        # 5. Create a ScrolledWindow to hold the button box.
        scrolled_window = Gtk.ScrolledWindow()
        # Set scrolling policy: Never horizontal, automatic vertical.
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        # --- MODIFIED: ADD VBOX TO SCROLLED WINDOW ---
        # 6. Add the box containing the buttons to the scrolled window.
        scrolled_window.add(buttons_vbox)

        # --- MODIFIED: ADD SCROLLED WINDOW TO THE MAIN BOX ---
        # 7. Add the scrolled_window (not the buttons_vbox) to the content area.
        #    The True, True parameters allow it to expand and fill the available space.
        box.pack_start(scrolled_window, True, True, 0)
        box.show_all()
        # 8. Send the initial sequence of commands to the new terminal tab
        initial_commands = [
            "echo '--- Initializing gNB CLI Interface ---'",
            "cd ~/UERANSIM/build",
            "ls",
            "sudo ./nr-cli UERANSIM-gnb-999-70-1"
        ]
        self.send_commands_sequentially(cli_terminal, initial_commands)
        
    def on_gnb_cli_command_clicked(self, button, terminal, command):
        """
        Handler to send a specific command string to a Vte.Terminal.
        It appends a newline character to execute the command.
        """
        if terminal:
            terminal.feed_child((command + "\n").encode())
            
    def on_ue_binaries(self, _):
        # Placeholder for UE control UI (if different from Network Overview)
        box = self.ue_area
        for c in box.get_children(): box.remove(c)
        box.pack_start(Gtk.Label(label="UE Control panel appears on the main Network Overview page."), True, True, 0)
        box.show_all()

    def on_ue_config(self, _):
        # Clear the gnb_area of any previous widgets, like the placeholder label
        box = self.ue_area
        for c in box.get_children(): box.remove(c)
        box.show_all()

        # Create a new terminal tab for this process
        terminal = self.create_terminal_tab("ue_config", "UE Configuration")

        # --- IMPORTANT ---
        # Define the commands and file paths you need.
        # These are placeholders; you must replace them with your actual paths and commands.
        config_dir = os.path.expanduser("./nr-gnb -c ../config/open5gs-ue.yaml")

        # This list contains the commands that will be run one-by-one.
        commands = [
            f"echo '--- Setting up gNB configuration ---'",
            f"cd UERANSIM",
            f"cd build",
            f"ls",
            f"{config_dir}"
        ]

        # Send the commands to the terminal
        self.send_commands_sequentially(terminal, commands)

    def on_ue_logs(self, _):
        log_dir = "/var/log/open5gs"
        if os.path.exists(log_dir):
            files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')])
        else:
            files = []
        
        box = self.core_area
        for child in box.get_children(): box.remove(child)

        listbox = Gtk.ListBox()
        for f in files:
            row = Gtk.ListBoxRow()
            btn = Gtk.Button(label=f, xalign=0)
            btn.connect("clicked", self.on_log_file_clicked, f)
            row.add(btn)
            listbox.add(row)
        
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(listbox)
        box.pack_start(scrolled_window, True, True, 15)
        box.show_all()

    def on_ue_cli(self, _):
        """
        Builds the UE CLI view with command buttons in the content area
        and a dedicated, reusable terminal in the bottom notebook.
        """
        # 1. Get the content area and clear any previous widgets
        box = self.ue_area
        for child in box.get_children():
            box.remove(child)

        # --- KEY CHANGE FOR UNIFORMITY ---
        # 2. Create the terminal in the bottom notebook using our existing helper.
        # This ensures it looks and feels like all other terminals.
        # We give it a unique key 'gnb_cli' so it can be reused.
        cli_terminal = self.create_terminal_tab("ue_cli", "UE CLI")

        # --- CUSTOMIZE YOUR COMMANDS HERE (No changes here) ---
        gnb_commands = [
            ("info | Show some informations about the UE", "info"),
            ("status | Show some status information about the UE", "status"),
            ("timers | Dump current status of the timers in the UE", "timers"),
            ("rls-state | Show status information about RLS", "rls-state"),
            ("coverage | Dump available cells and PLMNs in the coverage", "coverage"),
            ("ps-establish | Trigger a PDU session establishment procedure","ps-establish"),
            ("ps-list | List all PDU sessions","ps-list"),
            ("ps-release | Trigger a PDU session release procedure","ps-release"),
            ("ps-release-all | Trigger PDU session release procedures for all active sessions","ps-release-all"),
            ("deregister | Perform a de-registration by the UE","deregister")
        ]

        # 3. Create a horizontal box for the command buttons
        buttons_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        # 4. Create a button for each command and connect it to the terminal tab
        for label, command in gnb_commands:
            btn = Gtk.Button()
            label_widget=Gtk.Label(label=label)
            label_widget.set_xalign(0)
            btn.add(label_widget)
            # The handler now points to the terminal in the bottom notebook
            btn.connect("clicked", self.on_ue_cli_command_clicked, cli_terminal, command)
            buttons_vbox.pack_start(btn, False, False, 0)
        
        # --- NEW: CREATE A SCROLLED WINDOW ---
        # 5. Create a ScrolledWindow to hold the button box.
        scrolled_window = Gtk.ScrolledWindow()
        # Set scrolling policy: Never horizontal, automatic vertical.
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        # --- MODIFIED: ADD VBOX TO SCROLLED WINDOW ---
        # 6. Add the box containing the buttons to the scrolled window.
        scrolled_window.add(buttons_vbox)

        # --- MODIFIED: ADD SCROLLED WINDOW TO THE MAIN BOX ---
        # 7. Add the scrolled_window (not the buttons_vbox) to the content area.
        #    The True, True parameters allow it to expand and fill the available space.
        box.pack_start(scrolled_window, True, True, 0)
        box.show_all()
        # 8. Send the initial sequence of commands to the new terminal tab
        initial_commands = [
            "echo '--- Initializing UE CLI Interface ---'",
            "cd ~/UERANSIM/build",
            "ls",
            "sudo ./nr-cli --dump"
        ]
        self.send_commands_sequentially(cli_terminal, initial_commands)
        
    def on_ue_cli_command_clicked(self, button, terminal, command):
        """
        Handler to send a specific command string to a Vte.Terminal.
        It appends a newline character to execute the command.
        """
        if terminal:
            terminal.feed_child((command + "\n").encode())
        

    def create_box_with_start(self, title, handler, btn_label=None):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        lbl = Gtk.Label(label=title)
        lbl.get_style_context().add_class("header-title")
        lbl.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(lbl, False, False, 0)

        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        frame.get_style_context().add_class("content-box")
        lbl_ip = Gtk.Label(label="IP address goes here")
        lbl_ip.set_halign(Gtk.Align.CENTER)
        frame.add(lbl_ip)
        vbox.pack_start(frame, True, True, 0)

        btn = Gtk.Button(label=btn_label or f"{PLAY_SYMBOL} Start")
        btn.get_style_context().add_class("start-button")
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", handler)
        vbox.pack_start(btn, False, False, 0)
        return vbox

    def create_box_with_gnb_control(self, title):
        box = self.create_box_with_start(title, self.toggle_gnb_process)
        button = box.get_children()[-1]
        self.gnb_button_ref = button

        # If the gNB is already running, update the new button to reflect this state.
        if self.gnb_running:
            ctx = button.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")
            button.set_label(f"{STOP_SYMBOL} Stop")
            
        return box

    def create_box_with_ue_control(self, title):
        box = self.create_box_with_start(title, self.toggle_ue_process)
        button = box.get_children()[-1]
        self.ue_button_ref = button

        # If the UE is already running, update the new button to reflect this state.
        if self.ue_running:
            ctx = button.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")
            button.set_label(f"{STOP_SYMBOL} Stop")

        return box

    def on_gnb_terminated(self, terminal, status):
        """Signal handler for when the gNB terminal process exits."""
        # Use GLib.idle_add to safely update the UI from a signal handler
        GLib.idle_add(self.reset_gnb_button)

    def on_ue_terminated(self, terminal, status):
        """Signal handler for when the UE terminal process exits."""
        GLib.idle_add(self.reset_ue_button)
        
    def create_terminal_tab(self, key, title):
        # Part 1: Get or create the terminal and its frame
        if key in self.terminals:
            terminal_info = self.terminals[key]
            terminal = terminal_info['terminal']
            page_num = self.terminal_notebook.page_num(terminal_info['frame'])
            if page_num != -1:
                self.terminal_notebook.set_current_page(page_num)
        else:
            frame = Gtk.Frame()
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            lbl = Gtk.Label(label=title)
            lbl.set_xalign(0)
            btn_close = Gtk.Button(label="✖")
            header.pack_start(lbl, True, True, 0)
            header.pack_start(btn_close, False, False, 0)

            terminal = Vte.Terminal()
            terminal.set_scrollback_lines(1000)
            terminal.spawn_async(Vte.PtyFlags.DEFAULT, os.environ['HOME'], ["/bin/bash"], [], GLib.SpawnFlags.DEFAULT, None, None, -1, None, None)

            def close_tab(_):
                if key in ("gnb", "ue"):
                    terminal.feed_child(b'\x03')
                page = self.terminal_notebook.page_num(frame)
                if page != -1:
                    self.terminal_notebook.remove_page(page)
                if key == "gnb" and self.gnb_running:
                    self.reset_gnb_button()
                    self.gnb_terminal_ref = None
                elif key == "ue" and self.ue_running:
                    self.reset_ue_button()
                    self.ue_terminal_ref = None
                self.terminals.pop(key, None)

            btn_close.connect("clicked", close_tab)
            vbox.pack_start(header, False, False, 0)
            vbox.pack_start(terminal, True, True, 0)
            frame.add(vbox)
            self.terminal_notebook.append_page(frame, Gtk.Label(label=title))
            self.terminal_notebook.set_current_page(-1)
            self.terminals[key] = {'frame': frame, 'terminal': terminal}
        
        # Part 2: Shared logic that runs for both new and existing tabs
        self.terminal_notebook.show_all()
        return terminal

    def reset_gnb_button(self):
        self.gnb_running = False
        if self.gnb_button_ref:
            ctx = self.gnb_button_ref.get_style_context()
            ctx.remove_class("stop-button")
            ctx.add_class("start-button")
            self.gnb_button_ref.set_label(f"{PLAY_SYMBOL} Start")

    def reset_ue_button(self):
        self.ue_running = False
        if self.ue_button_ref:
            ctx = self.ue_button_ref.get_style_context()
            ctx.remove_class("stop-button")
            ctx.add_class("start-button")
            self.ue_button_ref.set_label(f"{PLAY_SYMBOL} Start")

    def start_5g_terminal(self, _):
        self.on_core_daemons(_)

    def send_commands_sequentially(self, terminal, commands, delay=1000):
        def type_next_command(idx):
            if idx >= len(commands):
                return False
            terminal.feed_child((commands[idx] + "\n").encode())
            GLib.timeout_add(delay, type_next_command, idx + 1)
            return False
        type_next_command(0)

    def toggle_gnb_process(self, _):
        if not self.gnb_running:
            terminal = self.create_terminal_tab("gnb", "gNB Setup")
            
            # --- NEW: Connect the signal to our handler ---
            terminal.connect("child-exited", self.on_gnb_terminated)

            self.gnb_terminal_ref = terminal
            self.gnb_running = True
            ctx = self.gnb_button_ref.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")
            self.gnb_button_ref.set_label(f"{STOP_SYMBOL} Stop")
            
            # --- MODIFIED: Use 'exec' to replace the shell process ---
            # This ensures 'child-exited' fires when the command ends.
            # NOTE: This works best if sudo does not require a password.
            commands = ["cd ~/UERANSIM/build", "exec sudo ./nr-gnb -c ../config/open5gs-gnb.yaml"]
            self.send_commands_sequentially(terminal, commands, delay=1000)
        else:
            if self.gnb_terminal_ref:
                self.gnb_terminal_ref.feed_child(b'\x03')
            # The button is now reset by the on_gnb_terminated signal handler,
            # but we keep this for the case where the user clicks the Stop button.
            self.reset_gnb_button()

    def toggle_ue_process(self, _):
        if not self.ue_running:
            terminal = self.create_terminal_tab("ue", "UE Setup")

            # --- NEW: Connect the signal to our handler ---
            terminal.connect("child-exited", self.on_ue_terminated)

            self.ue_terminal_ref = terminal
            self.ue_running = True
            ctx = self.ue_button_ref.get_style_context()
            ctx.remove_class("start-button")
            ctx.add_class("stop-button")
            self.ue_button_ref.set_label(f"{STOP_SYMBOL} Stop")

            # --- MODIFIED: Use 'exec' to replace the shell process ---
            commands = ["cd ~/UERANSIM/build", "exec sudo ./nr-ue -c ../config/open5gs-ue.yaml"]
            self.send_commands_sequentially(terminal, commands, delay=1000)
        else:
            if self.ue_terminal_ref:
                self.ue_terminal_ref.feed_child(b'\x03')
            self.reset_ue_button()

def simulation_test_bed_main():
    app = SimulationTestBedApp()
    app.connect("destroy", Gtk.main_quit)
    Gtk.main()

if __name__ == "__main__":
    simulation_test_bed_main()
