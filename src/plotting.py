import json
from matplotlib import colors

import matplotlib.pyplot as plt
from constants import MEDIA_BASE_PATH, ENV
import numpy as np
import pandas as pd
import seaborn as sns
from numpy.core.fromnumeric import mean

from utils import DSValueType, SimilarityMeasureType, load_single_tumor, load_reconstructed_tumor, calc_dice_coef, calc_l2_norm

sns.set_style("whitegrid")

DICE_DATA_PATH = '/home/marcel/Projects/uni/thesis/src/data/baseline_data/2021-09-30 19:47:08_comparison.json'
L2_DATA_PATH = '/home/marcel/Projects/uni/thesis/src/data/baseline_data/2021-10-06 22:33:30_comparison_l2.json'
MEDIA_BASE_PATH = MEDIA_BASE_PATH[ENV]


def load_json_data(path):
    data = {}
    with open(path) as json_file:
        data = json.load(json_file)
    return data


def plot_runtime_vs_threads_single_input(data):
    """
    input data is a dict: {
        '$thread_number':{
            'runtime': $total_seconds,
            'partner': $partner_tumor_id # must be the same for all
        },
    }
    """
    x_data = [k for k in data.keys()]
    y_data = [float(v['runtime']) for _, v in data.items()]
    objects = np.arange(len(x_data))
    plt.bar(objects, y_data, align='center', alpha=0.5)
    plt.xticks(objects, x_data)
    plt.xlabel('Number of processes')
    plt.ylabel('Runtime in seconds')
    plt.title('Process count and corresponding runtime for 50k synthetic tumors')

    plt.show()


def plot_runtime_vs_threads_dual_input(data_1, data_2):
    """
    input data is a dict: {
        '$thread_number':{
            'runtime': $total_seconds,
            'partner': $partner_tumor_id # must be the same for all
        },
    }
    """
    x_data_1 = [k for k in data_1.keys()]
    y_data_1 = [float(v['runtime']) for _, v in data_1.items()]
    # x_data_2 = [k for k in data_2.keys()]
    y_data_2 = [float(v['runtime']) for _, v in data_2.items()]
    objects = np.arange(len(x_data_1))
    # add legend
    colors = {'DICE': 'royalblue', 'L2': 'indigo'}
    labels = list(colors.keys())
    handles = [plt.Rectangle((0, 0), 1, 1, color=colors[label])
               for label in labels]
    plt.legend(handles, labels)

    plt.bar(objects, y_data_1, align='center',
            alpha=0.5, width=0.3, color='royalblue')
    plt.bar(objects + 0.3, y_data_2, align='center',
            alpha=0.5, width=0.3, color='indigo')
    plt.xticks(objects, x_data_1)
    plt.xlabel('Number of processes')
    plt.ylabel('Runtime in seconds')
    plt.title('Process count and corresponding runtime for 50k synthetic tumors')

    plt.show()


def plot_gt_enc_comp(enc: str, test_set_size: str, gt_metric: str):
    table = pd.read_csv(
        f"{MEDIA_BASE_PATH}/{enc}/{gt_metric}/{gt_metric}_gt_{enc}_comp_{test_set_size}.csv").to_numpy()
    # transform list strings to length
    for row in table:
        row[0] = int(row[0][3:6])
        row[1] = len(row[1].split(','))
        row[2] = len(row[2].split(','))
        row[3] = len(row[3].split(' '))
    df_table = pd.DataFrame(
        {'tumor': table[:, 0], 'intersection': table[:, 3]})
    df_table.astype({'tumor': 'int32'})
    df_table.sort_values(by='tumor')
    print(df_table)
    ax = sns.barplot(x='tumor', y='intersection', data=df_table)
    ax.set(xlabel='real tumor (tgmXXX_preop)',
           ylabel='#intersection in top 15', title=f'#Intersection between top 15 groundtruth and encoded \n Datasetsize={test_set_size}, {enc}\n groundtruth_metric={gt_metric}, encoded_metric=l2')
    plt.show()


def plot_gt_enc_rbo_scores():
    json_data = {}
    with open("/home/marcel/Projects/uni/thesis/media/rbo_comp_200_top_1.json") as file:
        json_data = json.load(file)
    lists = zip(json_data.keys(), json_data.values())
    df = pd.DataFrame(data=lists, columns=['tumor', 'rbo'])
    df['tumor'] = df['tumor'].apply(lambda c: int(c[3:6]))

    avg = mean(df['rbo'].to_list())
    print(avg)
    print(sum(df['rbo'].to_list()))

    ax = sns.barplot(x='tumor', y='rbo', data=df)
    ax.axhline(avg)
    ax.set(xlabel='real tumor (tgmXXX_preop)',
           ylabel='RBO of top 1', title='RBO score for top 1 groundtruth and encoded l2 comparison for a test dataset_size= 200')
    # plt.show()


def plot_enc4096_gt_best_matches(test_set_size: str, enc: str, gt_metric: str):
    json_data = {}
    with open(f"{MEDIA_BASE_PATH}/{enc}/{gt_metric}/{enc}_gt_match_pairs/testset_size_{test_set_size}.json") as file:
        json_data = json.load(file)
    tumors = []
    gt_indices = []
    for key in json_data.keys():
        tumors.append(key)
        gt_indices.append(json_data[key]['unencoded_rank'])
    print(f"{max(gt_indices)=}")
    print(f"{np.sum(np.array(gt_indices) == 0)=}")
    df = pd.DataFrame(columns=['tumor', 'gt_index'],
                      data=zip(tumors, gt_indices))
    df['tumor'] = df['tumor'].apply(lambda c: int(c[3:6]))
    ax = sns.barplot(x='tumor', y='gt_index', data=df)
    avg = (sum(gt_indices)/len(gt_indices))
    print(f"{avg=}")
    ax.axhline(avg)
    ax.text(0, avg + 0.05, str(avg)[:4])
    ax.set(
        title=f"Index in the groundtruth ranking of the best encoded match \n Datasetsize={test_set_size}, {enc}\n groundtruth_metric={gt_metric}, encoded_metric=l2\n #perfect matches:{np.sum(np.array(gt_indices) == 0)}, worst match index: {max(gt_indices)}",)
    plt.show()


def plot_best_match_presence(enc: str, test_set_size: str, gt_metric: str, top_n: int, ax):
    from autoencoder.encoded_similarity_check import load_top_15_lists
    tumor_ids, gt_lists, encoded_lists = load_top_15_lists(
        csv_path=f"{MEDIA_BASE_PATH}/{enc}/{gt_metric}/{gt_metric}_gt_{enc}_comp_{test_set_size}.csv")
    # transform list strings to length
    is_present = []
    for tumor, gt_list, enc_list in zip(tumor_ids, gt_lists, encoded_lists):
        enc_best = enc_list[0]
        encbest_in_top_n_gt = enc_best in gt_list[:top_n]
        is_present.append(float(encbest_in_top_n_gt))

    tumor_ids = [int(tumor[3:6]) for tumor in tumor_ids]
    avg = sum(is_present) / len(is_present)
    sns.barplot(ax=ax, x=tumor_ids, y=is_present, color="#2a9c2c")
    ax.axhline(avg)
    ax.text(0, avg + 0.05, str(avg*100)[:4] + "%")
    ax.set_title(
        f"encoded best match in top {top_n} gt matches")
    # plt.show()


def plot_best_match_presence_overview(enc: str, test_set_size: str, gt_metric: str):
    fig, axes = plt.subplots(3, 1, figsize=(15, 5), sharey=True)
    fig.suptitle(
        f'encoded best match present in gt top n ranking\n Datasetsize={test_set_size}, {enc}\n groundtruth_metric={gt_metric}, encoded_metric=l2')

    plot_best_match_presence(
        enc, test_set_size, gt_metric, top_n=15, ax=axes[0])
    plot_best_match_presence(
        enc, test_set_size, gt_metric, top_n=5, ax=axes[1])
    plot_best_match_presence(
        enc, test_set_size, gt_metric, top_n=1, ax=axes[2])

    plt.show()


def plot_downsampled_best_match_presence(tumor_ids, top_gt_list, top_downsampled_list, top_n: int, ax, value_type: DSValueType):

    is_present = []
    for gt, downsampled in zip(top_gt_list, top_downsampled_list):
        down_best = downsampled[0]
        down_best_in_top_n_gt = down_best in gt[:top_n]
        if top_n == 15 and not down_best_in_top_n_gt:
            # print(gt.index(down_best))
            print("test")
        is_present.append(float(down_best_in_top_n_gt))
    tumor_ids = [int(tumor[3:6]) for tumor in tumor_ids]
    x_ax = np.linspace(1, len(tumor_ids), 62)
    # avg = sum(is_present) / len(is_present)
    # sns.barplot(ax=ax, x=tumor_ids, y=is_present, color="#2a9c2c")
    # ax.axhline(avg)
    # ax.text(0, avg + 0.05, str(avg*100)[:4] + "%")
    # ax.set(xticklabels=[])
    cmap = colors.ListedColormap(['red', 'green'])
    assignedColors = [cmap(int(t)) for t in is_present]
    # plt.cm.get_cmap('RdBu'))
    plot = sns.scatterplot(ax=ax, x=x_ax, y=is_present,
                           c=assignedColors,  cmap=cmap)  # marker='d',
    plot.set_yticks([1.0, 0.0], ["True",
                                 "False"])
    plot.set_xticklabels([])
    plot.set_xlabel("Tumors")
    avg = sum(is_present) / len(is_present)
    print(cmap(1))
    legend = plot.legend([str(avg*100)[:4] + "%"], loc="center right")
    legend.legendHandles[0].set_color('green')
    # ax.autoscale_view()
    # plot.set_ylabel("best match in top n")
    # ax.set_title(
    #     f"down sampled best match in top {top_n} gt matches, value_type={value_type}")
    # plt.show()


def plot_downsampled_best_match_presence_overview(testset_size: str, metric: SimilarityMeasureType):
    """testset_size only affects title, not the used dataset!"""
    fig, axes = plt.subplots(3, 2, sharex=True, sharey=True, figsize=(12, 3))
    rows = ["Top 1",
            "Top 5", "Top 15"]
    cols = [r"$64^3$", r"$32^3$"]
    for ax, col in zip(axes[0], cols):
        ax.set_title(col)
    for ax, row in zip(axes[:, 0], rows):
        ax.set_ylabel(row, rotation=0, size='large')

    # fig.suptitle(
    #     f'Down sampled best match present in gt top n ranking\n Datasetsize={testset_size}\n metric={metric}')
    from baseline import analysis

    # value_type = DSValueType.T1C
    # # T1C
    # tumor_ids, top_gt_list, top_downsampled_64_list = analysis.compare_best_match_for_downsampling(
    #     downsample_to=64, value_type=value_type, n_best=5)
    # _, _, top_downsampled_32_list = analysis.compare_best_match_for_downsampling(
    #     downsample_to=32, value_type=value_type, n_best=5)
    # plot_downsampled_best_match_presence(tumor_ids, top_gt_list,
    #                                      top_downsampled_list, top_n=3, ax=axes[0][0], value_type=value_type)
    # plot_downsampled_best_match_presence(tumor_ids, top_gt_list,
    #                                      top_downsampled_list, top_n=1, ax=axes[1][0], value_type=value_type)

    # # FLAIR
    # value_type = DSValueType.FLAIR
    # tumor_ids, top_gt_list, top_downsampled_list = analysis.compare_best_match_for_downsampling(
    #     downsample_to=64, value_type=value_type, n_best=5)
    # plot_downsampled_best_match_presence(tumor_ids, top_gt_list,
    #                                      top_downsampled_list, top_n=3, ax=axes[0][1], value_type=value_type)
    # plot_downsampled_best_match_presence(tumor_ids, top_gt_list,
    #  top_downsampled_list, top_n=1, ax=axes[1][1], value_type=value_type)

    # Combined
    fig.suptitle("DS FLAIR")
    value_type = DSValueType.FLAIR
    tumor_ids, top_gt_list, top_downsampled_64_list = analysis.compare_best_match_for_downsampling(
        downsample_to=64, value_type=value_type, n_best=15)
    _, _, top_downsampled_32_list = analysis.compare_best_match_for_downsampling(
        downsample_to=32, value_type=value_type, n_best=15)

    print(len(tumor_ids), len(top_gt_list), len(top_downsampled_64_list))
    plot_downsampled_best_match_presence(tumor_ids, top_gt_list,
                                         top_downsampled_64_list, top_n=1, ax=axes[0][0], value_type=value_type)
    plot_downsampled_best_match_presence(tumor_ids, top_gt_list,
                                         top_downsampled_64_list, top_n=5, ax=axes[1][0], value_type=value_type)
    plot_downsampled_best_match_presence(tumor_ids, top_gt_list,
                                         top_downsampled_64_list, top_n=15, ax=axes[2][0], value_type=value_type)
    plot_downsampled_best_match_presence(tumor_ids, top_gt_list,
                                         top_downsampled_32_list, top_n=1, ax=axes[0][1], value_type=value_type)
    plot_downsampled_best_match_presence(tumor_ids, top_gt_list,
                                         top_downsampled_32_list, top_n=5, ax=axes[1][1], value_type=value_type)
    plot_downsampled_best_match_presence(tumor_ids, top_gt_list,
                                         top_downsampled_32_list, top_n=15, ax=axes[2][1], value_type=value_type)

    fig.tight_layout()
    plt.show()


def test_mayavi():
    seg_type = 't1c'
    threshold = 0.2 if seg_type == 'flair' else 0.6
    base = load_single_tumor(
        tumor_id=3000, threshold=threshold)
    rec_path = "/Users/marcelrosier/Projects/uni/thesis/media/reconstructed_tumors/3000_reconstructed_2048.npy"
    rec = load_reconstructed_tumor(path=rec_path, threshold=threshold)

    print(calc_dice_coef(base, rec))
    print(calc_l2_norm(base, rec))
    # print(base.shape)
    # from mayavi import mlab
    # # contour3d(base)
    # mlab.clf()
    # x, y = np.mgrid[-10:10:100j, -10:10:100j]
    # r = np.sqrt(x**2 + y**2)
    # z = np.sin(r)/r
    # mlab.surf(z, warp_scale='auto')


# test_mayavi()
# plot_downsampled_best_match_presence_overview(
#     testset_size="50k", metric=SimilarityMeasureType.DICE)
# enc = "enc_FLAIR_1024_1500"
# gt_metric = 'l2'
# plot_best_match_presence_overview(
#     enc=enc, test_set_size="200", gt_metric=gt_metric)
# plot_best_match_presence_overview(
#     enc=enc, test_set_size="2k", gt_metric=gt_metric)
# plot_best_match_presence_overview(
#     enc=enc, test_set_size="20k", gt_metric=gt_metric)
# plot_gt_enc_comp(enc=enc, test_set_size="200", gt_metric=gt_metric)
# plot_gt_enc_comp(enc=enc, test_set_size="2k", gt_metric=gt_metric)
# plot_gt_enc_comp(enc=enc, test_set_size="20k", gt_metric=gt_metric)
# plot_enc4096_gt_best_matches(test_set_size="200", enc=enc, gt_metric=gt_metric)
# plot_enc4096_gt_best_matches(test_set_size="2k", enc=enc, gt_metric=gt_metric)
# plot_enc4096_gt_best_matches(test_set_size="20k", enc=enc, gt_metric=gt_metric)

# gt_metric = 'dice'
# plot_best_match_presence_overview(
#     enc=enc, test_set_size="200", gt_metric=gt_metric)
# plot_best_match_presence_overview(
#     enc=enc, test_set_size="2k", gt_metric=gt_metric)
# plot_best_match_presence_overview(
#     enc=enc, test_set_size="20k", gt_metric=gt_metric)
# plot_gt_enc_comp(enc=enc, test_set_size="200", gt_metric=gt_metric)
# plot_gt_enc_comp(enc=enc, test_set_size="2k", gt_metric=gt_metric)
# plot_gt_enc_comp(enc=enc, test_set_size="20k", gt_metric=gt_metric)
# plot_enc4096_gt_best_matches(test_set_size="200", enc=enc, gt_metric=gt_metric)
# plot_enc4096_gt_best_matches(test_set_size="2k", enc=enc, gt_metric=gt_metric)
# plot_enc4096_gt_best_matches(test_set_size="20k", enc=enc, gt_metric=gt_metric)

# 4096_1500


# 4096_3000


# names:
# best_match_comp_2k
# gt_vs_enc_2k
# best_match_comp_2k
