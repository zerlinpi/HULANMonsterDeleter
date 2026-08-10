"""Embedded user-provided photos assembled from source chunks."""

from photo_data.full_1 import DATA as F1
from photo_data.full_2 import DATA as F2
from photo_data.full_3 import DATA as F3
from photo_data.full_4 import DATA as F4
from photo_data.close_1 import DATA as C1
from photo_data.close_2 import DATA as C2
from photo_data.close_3 import DATA as C3
from photo_data.close_4 import DATA as C4

PHOTO_FULL_B64 = F1 + F2 + F3 + F4
PHOTO_CLOSE_B64 = C1 + C2 + C3 + C4
