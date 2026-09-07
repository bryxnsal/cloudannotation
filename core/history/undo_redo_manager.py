"""
Undo/Redo History Manager Module.
Encapsulates action history, snapshot states, and rollback capabilities for point classification.
"""
from typing import Optional, Tuple, Dict, Any, List
import numpy as np
import pandas as pd

class UndoRedoManager:
    """
    Manages undo/redo stacks for point cloud classification changes.
    """
    def __init__(self, max_steps: int = 50):
        self.max_steps = max_steps
        self.undo_stack: List[Dict[str, Any]] = []
        self.redo_stack: List[Dict[str, Any]] = []

    def record_action(
        self,
        indices: np.ndarray,
        old_classes: np.ndarray,
        new_class: int,
        selection_indices: Optional[List[int]] = None
    ) -> None:
        """
        Record a classification action onto the undo stack and reset the redo stack.
        """
        if len(indices) == 0:
            return

        self.undo_stack.append({
            'indices': indices,
            'old_classes': old_classes.copy(),
            'new_class': new_class,
            'selection_indices': list(selection_indices) if selection_indices is not None else []
        })

        if len(self.undo_stack) > self.max_steps:
            self.undo_stack.pop(0)

        self.redo_stack.clear()

    def undo(self, points_df: pd.DataFrame) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Revert the most recent action on points_df.
        Returns (success, message, action_metadata).
        """
        if not self.undo_stack:
            return False, "Nothing to undo", None

        action = self.undo_stack.pop()
        indices = action['indices']
        old_classes = action['old_classes']

        current_classes = points_df.loc[indices, 'class'].to_numpy(copy=True)
        self.redo_stack.append({
            'indices': indices,
            'old_classes': current_classes,
            'new_class': action['new_class'],
            'selection_indices': action.get('selection_indices', [])
        })

        points_df.loc[indices, 'class'] = old_classes
        return True, f"Undo: Restored {len(indices)} points to previous classes", action

    def redo(self, points_df: pd.DataFrame) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Re-apply the last undone action on points_df.
        Returns (success, message, action_metadata).
        """
        if not self.redo_stack:
            return False, "Nothing to redo", None

        action = self.redo_stack.pop()
        indices = action['indices']

        current_classes = points_df.loc[indices, 'class'].to_numpy(copy=True)
        self.undo_stack.append({
            'indices': indices,
            'old_classes': current_classes,
            'new_class': action['new_class'],
            'selection_indices': action.get('selection_indices', [])
        })

        points_df.loc[indices, 'class'] = action['new_class']
        return True, f"Redo: Re-applied class {action['new_class']} on {len(indices)} points", action

    def clear(self) -> None:
        """Clear both undo and redo histories."""
        self.undo_stack.clear()
        self.redo_stack.clear()
