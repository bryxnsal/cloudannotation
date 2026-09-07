"""
SelectionManager: Encapsulates point selection, highlight mask queries, and spatial relative index mapping.
"""
from typing import Optional, List, Union
import numpy as np
import pandas as pd
from Mask import Mask


class SelectionManager:
    """
    Manages selection filters (classes, rgb, user_data, intensity, viewer highlight)
    and coordinate relative index resolutions.
    """

    @staticmethod
    def get_relative_indices(mask: Mask, relative: Optional[Mask] = None) -> np.ndarray:
        """
        Return the chosen point indices relative to the currently rendered points (or some other set).
        """
        if relative is None:
            return mask.resolve()
        mask.bools = mask.bools[relative.bools]
        return mask.resolve()

    @staticmethod
    def get_highlighted_mask(total_points: int, viewer_adapter, showing: Mask, invert: bool = False) -> Mask:
        """
        Return a Mask indicating which points are currently highlighted in the viewer.
        """
        mask = Mask(total_points, False)
        if viewer_adapter and viewer_adapter.is_ready():
            selection = viewer_adapter.get_selected_indices()
            if selection is None or len(selection) == 0:
                if invert and showing is not None:
                    mask.bools = showing.bools.copy()
                return mask
            if invert:
                unselection = np.arange(0, total_points)
                unselection = unselection[np.in1d(unselection, selection, invert=True)]
                mask.setr_subset(unselection, showing)
                return mask
            else:
                mask.setr_subset(selection, showing)
                return mask
        return mask

    @staticmethod
    def select(points_df: pd.DataFrame,
               viewer_adapter=None,
               showing: Optional[Mask] = None,
               indices: Optional[Union[List[int], np.ndarray]] = None,
               highlighted: bool = True,
               showing_flag: bool = False,
               classes: Optional[Union[List[int], range]] = None,
               data: Optional[Union[List[int], range]] = None,
               intensity: Optional[Union[List[int], range]] = None,
               red: Optional[Union[List[int], range]] = None,
               green: Optional[Union[List[int], range]] = None,
               blue: Optional[Union[List[int], range]] = None,
               compliment: bool = False,
               invert: bool = False) -> Mask:
        """
        Select points based on criteria: indices, viewer highlight, showing mask, classes, user_data, intensity, rgb.
        """
        total = len(points_df)
        mask = Mask(total, True)
        cur_mask = Mask(total, False)

        if indices is not None and len(indices):
            mask.setr(indices)

        if highlighted and viewer_adapter and showing is not None:
            cur_mask = SelectionManager.get_highlighted_mask(total, viewer_adapter, showing, invert=invert)
            if cur_mask.count():
                mask.intersection(cur_mask.bools)

        if showing_flag and showing is not None and showing.bools is not None:
            mask.intersection(showing.bools)

        if classes is not None and 'class' in points_df.columns:
            cur_mask.false()
            for c in classes:
                cur_mask.union(points_df['class'] == c)
            mask.intersection(cur_mask.bools)

        if data is not None and 'user_data' in points_df.columns:
            cur_mask.false()
            for d in data:
                cur_mask.union(points_df['user_data'] == d)
            mask.intersection(cur_mask.bools)

        if intensity is not None and 'intensity' in points_df.columns:
            cur_mask.false()
            for i in intensity:
                cur_mask.union(points_df['intensity'] == i)
            mask.intersection(cur_mask.bools)

        if 'r' in points_df.columns:
            if red is not None:
                cur_mask.false()
                for r in red:
                    cur_mask.union(points_df['r'] == r)
                mask.intersection(cur_mask.bools)
            if green is not None:
                cur_mask.false()
                for g in green:
                    cur_mask.union(points_df['g'] == g)
                mask.intersection(cur_mask.bools)
            if blue is not None:
                cur_mask.false()
                for b in blue:
                    cur_mask.union(points_df['b'] == b)
                mask.intersection(cur_mask.bools)

        if compliment:
            mask.compliment()

        return mask
