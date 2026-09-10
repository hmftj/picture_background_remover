import os
from pathlib import Path
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk
from PIL import Image, ImageTk

from core.remover import (
    composite_background,
    export_image_bytes,
    get_session,
    load_and_normalize_image,
    remove_background,
    render_checkerboard_preview,
)


class RembgGUI:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Background Remover Pro")
        self.root.geometry("820x680")
        self.root.minsize(760, 620)

        # Dark theme palette
        self.BG_DARK = "#121212"
        self.FRAME_BG = "#1E1E1E"
        self.TEXT_COLOR = "#E0E0E0"
        self.TEXT_MUTED = "#888888"
        self.ACCENT_COLOR = "#007AFF"
        self.ACCENT_HOVER = "#005BB5"
        self.SUCCESS_COLOR = "#34C759"
        self.SUCCESS_HOVER = "#248A3D"
        self.DANGER_COLOR = "#FF3B30"
        self.DISABLED_BG = "#2C2C2C"
        self.DISABLED_FG = "#555555"

        self.root.configure(bg=self.BG_DARK)

        # State variables
        self.input_path: str | None = None
        self.original_img: Image.Image | None = None
        self.raw_output_img: Image.Image | None = None  # Transparent RGBA cutout
        self.final_output_img: Image.Image | None = None  # With optional background fill
        self.bg_choice = tk.StringVar(value="Transparent")
        self.custom_bg_hex = "#FFFFFF"
        self.is_closing = False
        self.is_processing = False

        # Session preloading (lazy in background)
        self.session = None
        threading.Thread(target=self._preload_session, daemon=True).start()

        # Handle window closing cleanly
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()

    def _preload_session(self):
        try:
            self.session = get_session(force_cpu=True)
        except Exception:
            pass

    def on_close(self):
        self.is_closing = True
        self.root.destroy()

    def _build_ui(self):
        # 1. Header Title
        title_frame = tk.Frame(self.root, bg=self.BG_DARK)
        title_frame.pack(fill="x", padx=30, pady=(15, 10))

        title_label = tk.Label(
            title_frame,
            text="✨ Background Remover Pro",
            font=("Segoe UI", 20, "bold"),
            fg=self.TEXT_COLOR,
            bg=self.BG_DARK,
        )
        title_label.pack(side="left")

        # 2. File Selection Bar
        top_frame = tk.Frame(self.root, bg=self.BG_DARK)
        top_frame.pack(fill="x", padx=30, pady=5)

        self.btn_select = tk.Button(
            top_frame,
            text="📂 Choose Image",
            font=("Segoe UI", 10, "bold"),
            bg=self.ACCENT_COLOR,
            fg="white",
            activebackground=self.ACCENT_HOVER,
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=7,
            command=self.select_image,
        )
        self.btn_select.pack(side="left")

        self.lbl_path = tk.Label(
            top_frame,
            text="No file selected...",
            font=("Segoe UI", 10),
            fg=self.TEXT_MUTED,
            bg=self.BG_DARK,
            anchor="w",
        )
        self.lbl_path.pack(side="left", padx=15, fill="x", expand=True)

        self.btn_reset = tk.Button(
            top_frame,
            text="🔄 Reset",
            font=("Segoe UI", 9),
            bg=self.DISABLED_BG,
            fg=self.TEXT_MUTED,
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=6,
            command=self.reset_state,
        )
        self.btn_reset.pack(side="right")

        # 3. Preview Container (Cards for Original & Result)
        preview_container = tk.Frame(self.root, bg=self.BG_DARK)
        preview_container.pack(fill="both", expand=True, padx=30, pady=10)

        # Original Card
        orig_card = tk.LabelFrame(
            preview_container,
            text=" Original Image ",
            font=("Segoe UI", 10, "bold"),
            fg=self.TEXT_COLOR,
            bg=self.FRAME_BG,
            bd=1,
            relief="solid",
        )
        orig_card.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="nsew")

        self.lbl_orig = tk.Label(
            orig_card,
            text="Image preview will appear here",
            font=("Segoe UI", 10),
            fg=self.TEXT_MUTED,
            bg=self.FRAME_BG,
        )
        self.lbl_orig.pack(expand=True, fill="both", padx=10, pady=10)

        # Result Card
        result_card = tk.LabelFrame(
            preview_container,
            text=" Processed Result ",
            font=("Segoe UI", 10, "bold"),
            fg=self.TEXT_COLOR,
            bg=self.FRAME_BG,
            bd=1,
            relief="solid",
        )
        result_card.grid(row=0, column=1, padx=(10, 0), pady=5, sticky="nsew")

        self.lbl_result = tk.Label(
            result_card,
            text="Processed cutout will appear here",
            font=("Segoe UI", 10),
            fg=self.TEXT_MUTED,
            bg=self.FRAME_BG,
        )
        self.lbl_result.pack(expand=True, fill="both", padx=10, pady=10)

        preview_container.grid_columnconfigure(0, weight=1)
        preview_container.grid_columnconfigure(1, weight=1)
        preview_container.grid_rowconfigure(0, weight=1)

        # 4. Background Fill Options Bar
        opts_frame = tk.LabelFrame(
            self.root,
            text=" Background Options ",
            font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_COLOR,
            bg=self.FRAME_BG,
            bd=1,
            relief="solid",
        )
        opts_frame.pack(fill="x", padx=30, pady=(5, 10))

        tk.Radiobutton(
            opts_frame,
            text="Transparent",
            variable=self.bg_choice,
            value="Transparent",
            command=self.on_bg_option_change,
            bg=self.FRAME_BG,
            fg=self.TEXT_COLOR,
            selectcolor=self.BG_DARK,
            activebackground=self.FRAME_BG,
            activeforeground=self.TEXT_COLOR,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=15, pady=5)

        tk.Radiobutton(
            opts_frame,
            text="Solid White",
            variable=self.bg_choice,
            value="Solid White",
            command=self.on_bg_option_change,
            bg=self.FRAME_BG,
            fg=self.TEXT_COLOR,
            selectcolor=self.BG_DARK,
            activebackground=self.FRAME_BG,
            activeforeground=self.TEXT_COLOR,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=10, pady=5)

        tk.Radiobutton(
            opts_frame,
            text="Solid Black",
            variable=self.bg_choice,
            value="Solid Black",
            command=self.on_bg_option_change,
            bg=self.FRAME_BG,
            fg=self.TEXT_COLOR,
            selectcolor=self.BG_DARK,
            activebackground=self.FRAME_BG,
            activeforeground=self.TEXT_COLOR,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=10, pady=5)

        self.btn_pick_color = tk.Button(
            opts_frame,
            text="🎨 Custom Color...",
            font=("Segoe UI", 9),
            bg="#333333",
            fg=self.TEXT_COLOR,
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=2,
            command=self.pick_custom_color,
        )
        self.btn_pick_color.pack(side="left", padx=15, pady=5)

        # 5. Status Label
        self.lbl_status = tk.Label(
            self.root,
            text="Ready. Please select an image to begin.",
            font=("Segoe UI", 10),
            fg=self.TEXT_MUTED,
            bg=self.BG_DARK,
        )
        self.lbl_status.pack(pady=4)

        # 6. Bottom Action Buttons
        bottom_frame = tk.Frame(self.root, bg=self.BG_DARK)
        bottom_frame.pack(fill="x", padx=30, pady=(5, 20))

        self.btn_remove = tk.Button(
            bottom_frame,
            text="✨ Remove Background",
            font=("Segoe UI", 11, "bold"),
            bg=self.DISABLED_BG,
            fg=self.DISABLED_FG,
            activebackground=self.ACCENT_HOVER,
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            pady=10,
            state="disabled",
            command=self.start_removal_thread,
        )
        self.btn_remove.pack(side="left", expand=True, fill="x", padx=(0, 10))

        self.btn_save = tk.Button(
            bottom_frame,
            text="💾 Save Result",
            font=("Segoe UI", 11, "bold"),
            bg=self.DISABLED_BG,
            fg=self.DISABLED_FG,
            activebackground=self.SUCCESS_HOVER,
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            pady=10,
            state="disabled",
            command=self.save_image,
        )
        self.btn_save.pack(side="right", expand=True, fill="x", padx=(10, 0))

    def reset_state(self):
        """Reset UI and loaded image state."""
        self.input_path = None
        self.original_img = None
        self.raw_output_img = None
        self.final_output_img = None
        self.bg_choice.set("Transparent")

        self.lbl_path.config(text="No file selected...", fg=self.TEXT_MUTED)
        self.lbl_orig.config(image="", text="Image preview will appear here")
        self.lbl_result.config(image="", text="Processed cutout will appear here")
        self.lbl_status.config(text="Ready. Please select an image to begin.", fg=self.TEXT_MUTED)

        self.btn_remove.config(state="disabled", bg=self.DISABLED_BG, fg=self.DISABLED_FG)
        self.btn_save.config(state="disabled", bg=self.DISABLED_BG, fg=self.DISABLED_FG)

    def select_image(self):
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Image Files", "*.jpg;*.jpeg;*.png;*.webp;*.bmp"),
                ("JPEG Images", "*.jpg;*.jpeg"),
                ("PNG Images", "*.png"),
                ("All Files", "*.*"),
            ]
        )

        if not file_path:
            return

        try:
            self.input_path = file_path
            self.original_img = load_and_normalize_image(file_path)

            display_name = os.path.basename(file_path)
            if len(display_name) > 35:
                display_name = display_name[:32] + "..."

            self.lbl_path.config(
                text=f"{display_name} ({self.original_img.width}×{self.original_img.height} px)",
                fg=self.TEXT_COLOR,
            )

            # Generate preview keeping aspect ratio
            orig_thumb = self.original_img.copy()
            orig_thumb.thumbnail((280, 280), Image.Resampling.LANCZOS)
            self.tk_orig = ImageTk.PhotoImage(orig_thumb)
            self.lbl_orig.config(image=self.tk_orig, text="")

            self.lbl_result.config(image="", text="Click 'Remove Background' to process...")
            self.raw_output_img = None
            self.final_output_img = None

            self.btn_remove.config(state="normal", bg=self.ACCENT_COLOR, fg="white")
            self.btn_save.config(state="disabled", bg=self.DISABLED_BG, fg=self.DISABLED_FG)
            self.lbl_status.config(text="Image loaded successfully. Ready to process.", fg=self.TEXT_COLOR)

        except Exception as e:
            messagebox.showerror("Error Loading Image", f"Could not load image:\n{e}")

    def pick_custom_color(self):
        """Allow user to choose custom background fill."""
        color = colorchooser.askcolor(title="Choose Background Color", initialcolor=self.custom_bg_hex)
        if color and color[1]:
            self.custom_bg_hex = color[1]
            self.bg_choice.set("Custom")
            self.btn_pick_color.config(text=f"🎨 Color: {self.custom_bg_hex}")
            self.update_result_display()

    def on_bg_option_change(self):
        self.btn_pick_color.config(text="🎨 Custom Color...")
        self.update_result_display()

    def update_result_display(self):
        """Update result preview when background choice changes without re-running rembg."""
        if self.raw_output_img is None or self.is_closing:
            return

        choice = self.bg_choice.get()
        if choice == "Solid White":
            self.final_output_img = composite_background(self.raw_output_img, "#FFFFFF")
        elif choice == "Solid Black":
            self.final_output_img = composite_background(self.raw_output_img, "#000000")
        elif choice == "Custom":
            self.final_output_img = composite_background(self.raw_output_img, self.custom_bg_hex)
        else:
            self.final_output_img = self.raw_output_img

        # Render checkered preview if transparent, or direct preview if solid
        if choice == "Transparent":
            preview = render_checkerboard_preview(self.final_output_img, max_size=(280, 280))
        else:
            preview = self.final_output_img.copy()
            preview.thumbnail((280, 280), Image.Resampling.LANCZOS)

        self.tk_result = ImageTk.PhotoImage(preview)
        self.lbl_result.config(image=self.tk_result, text="")

    def start_removal_thread(self):
        if self.is_processing:
            return

        self.is_processing = True
        self.btn_remove.config(state="disabled", bg=self.DISABLED_BG, fg=self.DISABLED_FG)
        self.btn_select.config(state="disabled", bg=self.DISABLED_BG, fg=self.DISABLED_FG)
        self.btn_save.config(state="disabled", bg=self.DISABLED_BG, fg=self.DISABLED_FG)

        self.lbl_status.config(text="⏳ Removing background, please wait...", fg="#5AC8FA")

        threading.Thread(target=self._process_worker, daemon=True).start()

    def _process_worker(self):
        try:
            if self.session is None:
                self.session = get_session(force_cpu=True)

            out_img = remove_background(self.original_img, session=self.session)

            if not self.is_closing:
                self.root.after(0, lambda: self._on_process_success(out_img))
        except Exception as e:
            if not self.is_closing:
                self.root.after(0, lambda: self._on_process_error(str(e)))

    def _on_process_success(self, out_img: Image.Image):
        self.is_processing = False
        if self.is_closing:
            return

        self.raw_output_img = out_img
        self.update_result_display()

        self.lbl_status.config(text="✔ Background removed successfully!", fg=self.SUCCESS_COLOR)

        self.btn_select.config(state="normal", bg=self.ACCENT_COLOR, fg="white")
        self.btn_remove.config(state="normal", bg=self.ACCENT_COLOR, fg="white")
        self.btn_save.config(state="normal", bg=self.SUCCESS_COLOR, fg="white")

    def _on_process_error(self, err_msg: str):
        self.is_processing = False
        if self.is_closing:
            return

        self.btn_select.config(state="normal", bg=self.ACCENT_COLOR, fg="white")
        self.btn_remove.config(state="normal", bg=self.ACCENT_COLOR, fg="white")

        self.lbl_status.config(text="✖ Error occurred during processing.", fg=self.DANGER_COLOR)
        messagebox.showerror("Processing Error", f"Failed to remove background:\n{err_msg}")

    def save_image(self):
        if self.final_output_img is None:
            return

        # Infer initial filename from input path
        initial_name = "processed_image_no_bg.png"
        if self.input_path:
            stem = Path(self.input_path).stem
            initial_name = f"{stem}_no_bg.png"

        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG Image (*.png)", "*.png"),
                ("JPEG Image (*.jpg;*.jpeg)", "*.jpg;*.jpeg"),
                ("WEBP Image (*.webp)", "*.webp"),
            ],
            initialfile=initial_name,
        )

        if not save_path:
            return

        try:
            ext = Path(save_path).suffix.lower()
            fmt = "PNG"
            if ext in (".jpg", ".jpeg"):
                fmt = "JPEG"
            elif ext == ".webp":
                fmt = "WEBP"

            fill_color = self.custom_bg_hex if self.bg_choice.get() == "Custom" else "#FFFFFF"
            data, _, _ = export_image_bytes(
                self.final_output_img,
                format=fmt,
                bg_fill=fill_color,
            )

            with open(save_path, "wb") as f:
                f.write(data)

            messagebox.showinfo("Success", f"Image saved successfully to:\n{save_path}")
            self.lbl_status.config(
                text=f"✔ Saved: {os.path.basename(save_path)}",
                fg=self.SUCCESS_COLOR,
            )
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save image:\n{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = RembgGUI(root)
    root.mainloop()