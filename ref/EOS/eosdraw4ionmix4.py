import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from basefunctions.io_ionmix4 import read_ionmix4

def convert_density_to_gcc(density_list, conversion_factor):
    """将密度单位转换为 g/cc"""
    return [density * conversion_factor for density in density_list]

def log10_transform(data_list):
    """对数据列表进行 log10 变换"""
    return np.log10(data_list)

def prepare_surface_data(x_list, y_list, z_data, xlim, ylim, clip_data):
    """准备三维曲面数据，并根据需要裁剪超出范围的数据"""
    X, Y = np.meshgrid(np.log10(x_list), np.log10(y_list))
    
    # 将 z_data 转换为 numpy 数组以便进行高效的数学运算
    z_array = np.asarray(z_data, dtype=float)

    # 创建一个副本以进行安全操作，避免修改原始数据
    z_safe = z_array.copy()
    
    # 找到所有小于或等于 0 的值
    non_positive_mask = z_safe <= 0
    
    # 将这些无效值替换为 NaN (Not a Number)。
    # Matplotlib 在绘图时会自动忽略 NaN 点，从而产生空洞而不是毛刺。
    z_safe[non_positive_mask] = 1e-30  # 使用一个非常小的正数代替

    # 现在可以安全地进行 log10 变换
    Z = np.log10(z_safe)


    if clip_data:
        # 裁剪数据
        mask_x = (X >= xlim[0]) & (X <= xlim[1])
        mask_y = (Y >= ylim[0]) & (Y <= ylim[1])
        mask = mask_x & mask_y

        X = np.where(mask, X, np.nan)  # 超出范围的数据设置为 NaN
        Y = np.where(mask, Y, np.nan)
        Z = np.where(mask, Z, np.nan)

    return X, Y, Z

def plot_surface(ax, X, Y, Z, title, xlabel, ylabel, cmap='viridis'):
    """绘制三维曲面"""
    ax.plot_surface(X, Y, Z, cmap=cmap)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

def main(filename, atomic_weight, clip_data, xlim=None, ylim=None):
    # 读取数据
    data_block = read_ionmix4(filename)
    NR = data_block[1]
    T_list = data_block[3]
    rho_list = data_block[4]
    Ei_list = data_block[8]
    Pi_list = data_block[6]
    Ee_list = data_block[9]
    Pe_list = data_block[7]
    charge_list = data_block[10]

    # 转换密度单位
    mAl = (1.993 * atomic_weight / 12) * 1e-23
    rhoN_list = rho_list #原始数密度表
    rho_list = convert_density_to_gcc(rho_list, mAl)

    # 打印调试信息
    print(f"rho_min: {rho_list[0]}, rho_max: {rho_list[-1]}g/cc")
    print(f"NumberRho_min: {rhoN_list[0]}, NumberRho_max: {rhoN_list[-1]} /cc")
    print(f"T_min: {T_list[0]}, T_max: {T_list[-1]} eV")
    print(f"charge_list[0][0]: {charge_list[0][0]}")
    print(f"len(rho_list): {len(rho_list)}")
    print(f"len(T_list): {len(T_list)}")

    # 准备三维数据
    datasets = {
        "Ei": Ei_list,
        "Pi": Pi_list,
        "Ee": Ee_list,
        "Pe": Pe_list,
        "Z": charge_list,
    }

    # 创建图形
    fig = plt.figure()
    axes = [fig.add_subplot(2, 3, i + 1, projection='3d') for i in range(len(datasets))]

    # 绘制每个数据集的三维曲面
    for ax, (title, z_data) in zip(axes, datasets.items()):
        X, Y, Z = prepare_surface_data(T_list, rho_list, z_data, xlim, ylim, clip_data)
        plot_surface(ax, X, Y, Z, title, xlabel='T (eV)', ylabel='rho (g/cc)')

    # 显示图形
    plt.show()

if __name__ == "__main__":
    # filename = 'outputfiles/Al-0509.cn4'
    # filename = 'outputfiles/al-imx-003.cn4'
    # atomic_weight = 26.9815 
    # atomic_weight = 4.0026 
    # filename = 'outputfiles/He_TF_C_treat.cn4'
    # filename = 'inputfiles/He-TFeos.cn4'
    # filename = 'outputfiles/He_hybrid-eos.cn4'
    # filename = 'outputfiles/He-TFeos-treat.cn4'
    # filename = 'inputfiles/he-imx-005.cn4'
    filename = 'outputfiles/N_TF_C_treat.cn4'
    # filename = 'outputfiles/N_tops.cn4'。
    atomic_weight = 14.0067

    # 设置是否裁剪数据
    clip_data = False  # 如果不想裁剪数据，将其设置为 False
    # 设置裁剪范围
    # xlim = (np.log10(2), np.log10(2e5))
    # ylim = (np.log10(6.647651e-8), np.log10(6.647651e-4))
    main(filename, atomic_weight, clip_data)