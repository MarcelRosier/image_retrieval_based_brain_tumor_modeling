import json
import multiprocessing
import os
from datetime import datetime
from functools import partial
from typing import Tuple
from monai.metrics import compute_meandice
from monai.losses.dice import DiceLoss
import numpy as np
import torch
import utils
from constants import (BASELINE_SIMILARITY_BASE_PATH, ENV, REAL_TUMOR_PATH,
                       SYN_TUMOR_BASE_PATH, SYN_TUMOR_PATH_TEMPLATE)
from scipy.ndimage import zoom
from utils import (SimilarityMeasureType, load_real_tumor,
                   time_measure)

REAL_TUMOR_PATH = REAL_TUMOR_PATH[ENV]
SYN_TUMOR_BASE_PATH = SYN_TUMOR_BASE_PATH[ENV]
SYN_TUMOR_PATH_TEMPLATE = SYN_TUMOR_PATH_TEMPLATE[ENV]
BASELINE_SIMILARITY_BASE_PATH = BASELINE_SIMILARITY_BASE_PATH[ENV]


def get_scores_for_pair(measure_func, t1c, flair, downsample_to, tumor_folder):
    """
    Calculate the similarity score of the passed tumor pair
    """

    # load tumor data
    tumor = np.load(SYN_TUMOR_PATH_TEMPLATE.format(
        id=tumor_folder))['data']

    # crop 129^3 to 128^3 if needed
    if tumor.shape != (128, 128, 128):
        tumor = np.delete(np.delete(
            np.delete(tumor, 128, 0), 128, 1), 128, 2)

    if downsample_to:
        tumor = zoom(tumor, zoom=downsample_to/128, order=0)
    # normalize
    max_val = tumor.max()
    if max_val != 0:
        tumor *= 1.0/max_val

    # threshold
    tumor_02 = np.copy(tumor)
    tumor_02[tumor_02 < 0.2] = 0
    tumor_02[tumor_02 >= 0.2] = 1
    tumor_06 = np.copy(tumor)
    tumor_06[tumor_06 < 0.6] = 0
    tumor_06[tumor_06 >= 0.6] = 1

    # calc and update dice scores and partners
    if not measure_func:
        criterion = DiceLoss(
            smooth_nr=0, smooth_dr=1e-5, to_onehot_y=False, sigmoid=False)
        tumor_02 = torch.from_numpy(tumor_02)
        tumor_02.unsqueeze_(0)
        tumor_02.unsqueeze_(0)
        flair = torch.from_numpy(flair)
        flair.unsqueeze_(0)
        flair.unsqueeze_(0)
        # cur_flair = compute_meandice(
        #     tumor_02, flair, include_background=False)
        cur_flair = criterion(tumor_02, flair)

        tumor_06 = torch.from_numpy(tumor_06)
        tumor_06.unsqueeze_(0)
        tumor_06.unsqueeze_(0)
        t1c = torch.from_numpy(t1c)
        t1c.unsqueeze_(0)
        t1c.unsqueeze_(0)
        # cur_t1c = compute_meandice(tumor_06, t1c, include_background=False)
        cur_t1c = criterion(tumor_06, t1c)
        cur_flair = 1 - cur_flair.item()
        cur_t1c = 1 - cur_t1c.item()
    else:
        cur_flair = measure_func(tumor_02, flair)
        cur_t1c = measure_func(tumor_06, t1c)
    combined = cur_t1c + cur_flair
    scores = {}
    scores[tumor_folder] = {
        't1c': cur_t1c,
        'flair': cur_flair,
        'combined': combined
    }
    return scores


@time_measure(log=True)
def get_scores_for_real_tumor_parallel(similarity_measure: SimilarityMeasureType, processes: int, tumor_path: str, subset: Tuple = None, downsample_to: int = None):
    """
    Calculate the best similarity measure score of the given tumor based on the given dataset and return tuple (scores, best_score)
    @similarity_measure determines the used comparison function 
    scores - dump of the individual scores
    best_score - info about the best combined score
    """
    (t1c, flair) = load_real_tumor(tumor_path, downsample_to=downsample_to)

    folders = os.listdir(SYN_TUMOR_BASE_PATH)
    folders = [f for f in folders if f.isnumeric()]
    folders.sort(key=lambda f: int(f))
    # cap test set to 50k
    folders = folders[:50000]
    if subset is not None:
        folders = folders[subset[0]: subset[1]]
    print(f"{len(folders)=}, {subset=}")
    scores = {}

    print("Starting parallel loop for {} folders with {} processes".format(
        len(folders), processes))

    measure_func = None if similarity_measure == SimilarityMeasureType.DICE else utils.calc_l2_norm
    func = partial(get_scores_for_pair, measure_func,
                   t1c, flair, downsample_to)
    # with multiprocessing.Pool(processes) as pool:
    #     results = pool.map_async(func, folders)
    #     single_scores = results.get()
    #     scores = {k: v for d in single_scores for k, v in d.items()}
    scores = {}
    for f in folders:
        r = func(f)
        scores[f] = r[f]

    # find best
    best_key = 0
    if similarity_measure == SimilarityMeasureType.DICE:
        best_key = max(scores.keys(), key=lambda k: scores[k]['combined'])
    elif similarity_measure == SimilarityMeasureType.L2:
        best_key = min(scores.keys(), key=lambda k: scores[k]['combined'])

    best_score = {
        'best_score': scores[best_key],
        'partner': best_key
    }
    return scores, best_score


def run(processes, similarity_measure_type=SimilarityMeasureType.DICE, tumor_path=REAL_TUMOR_PATH, subset=None, downsample_to: int = None, save: bool = True):
    scores, best_score = get_scores_for_real_tumor_parallel(
        similarity_measure=similarity_measure_type,
        processes=processes,
        tumor_path=tumor_path,
        subset=subset,
        downsample_to=downsample_to)
    print(best_score)
    # now_date = datetime.now().strftime("%Y-%m-%d")
    # now_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # filename_dump = "data/{date}/{datetime}_parallel_datadump_{metric}.json".format(
    #     date=now_date, datetime=now_datetime, metric=similarity_measure_type.value)
    testset_size = "50k"
    if subset:
        testset_size = str(subset[1] - subset[0])

    if not save:
        return best_score
    tumor_id = tumor_path.split('/')[-1]
    sub_path = f"monai_dice/{testset_size}/dim_{downsample_to if downsample_to else 128}/{'dice' if similarity_measure_type==SimilarityMeasureType.DICE else 'l2'}/{tumor_id}.json"
    save_path = os.path.join(BASELINE_SIMILARITY_BASE_PATH, sub_path)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "w") as file:
        json.dump(scores, file)

    # filename_best = "data/{date}/{datetime}_parallel_best_{metric}.json".format(
    #     date=now_date, datetime=now_datetime, metric=similarity_measure_type.value)
    # os.makedirs(os.path.dirname(filename_best), exist_ok=True)

    # with open(filename_best, "w") as file:
    #     json.dump(best_score, file)
    return best_score
