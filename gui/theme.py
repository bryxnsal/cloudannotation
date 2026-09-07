"""
Theme and style configuration for ModernAnnotationGUI.
Centralizes color palette and ttk styles.
"""
from tkinter import ttk

# Global Modern Dark Palette
COLORS = {
    'bg_primary': '#2b2b2b',
    'bg_secondary': '#3c3c3c',
    'bg_accent': '#4a4a4a',
    'text_primary': '#ffffff',
    'text_secondary': '#cccccc',
    'accent': '#007acc',
    'success': '#4caf50',
    'warning': '#ff9800',
    'error': '#f44336',
    'border': '#555555'
}

def apply_theme(root):
    """
    Configure modern ttk styles with readable fonts and dark theme.
    """
    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except Exception:
        pass

    # Frame styles
    style.configure('Modern.TFrame', background=COLORS['bg_secondary'])
    style.configure('Accent.TFrame', background=COLORS['bg_accent'])

    # Labelframe styles
    style.configure('Modern.TLabelframe', 
                    background=COLORS['bg_secondary'], 
                    bordercolor=COLORS['border'])
    style.configure('Modern.TLabelframe.Label', 
                    background=COLORS['bg_secondary'], 
                    foreground=COLORS['text_primary'], 
                    font=('Segoe UI', 10, 'bold'))

    # Label styles
    style.configure('Modern.TLabel', 
                    background=COLORS['bg_secondary'], 
                    foreground=COLORS['text_primary'], 
                    font=('Segoe UI', 10))
    style.configure('Title.TLabel', 
                    background=COLORS['bg_secondary'], 
                    foreground=COLORS['text_primary'], 
                    font=('Segoe UI', 10, 'bold'))

    # Button styles
    style.configure('Modern.TButton', 
                    font=('Segoe UI', 10), 
                    padding=4)
    style.configure('Accent.TButton', 
                    font=('Segoe UI', 10, 'bold'), 
                    padding=4)

    # Checkbutton styles
    style.configure('Modern.TCheckbutton', 
                    background=COLORS['bg_secondary'],
                    foreground=COLORS['text_primary'], 
                    font=('Segoe UI', 10))

    # Progressbar styles
    style.configure('Modern.Horizontal.TProgressbar', 
                    background=COLORS['accent'], 
                    troughcolor=COLORS['bg_primary'],
                    bordercolor=COLORS['border'],
                    lightcolor=COLORS['accent'],
                    darkcolor=COLORS['accent'])

    # Treeview styles (for modals and tables)
    style.configure('Treeview',
                    background='#333333',
                    foreground='#ffffff',
                    fieldbackground='#333333',
                    rowheight=24,
                    font=('Segoe UI', 9))
    style.configure('Treeview.Heading',
                    background='#444444',
                    foreground='#ffffff',
                    font=('Segoe UI', 9, 'bold'))
    style.map('Treeview',
              background=[('selected', COLORS['accent'])],
              foreground=[('selected', '#ffffff')])

    return style
