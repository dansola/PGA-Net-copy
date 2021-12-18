import os
import sys
import time

from torchvision.models.segmentation import lraspp_mobilenet_v3_large, deeplabv3_mobilenet_v3_large

from src.models.dsc.dsc_lbc_unet import SkinnyDSCSmallUNetLBP, SuperSkinnyDSCSmallUNetLBP, DSCUNetLBP
from src.models.dsc.dsc_unet import UNetDSC, SmallUNetDSC, SkinnySmallUNetDSC
from src.models.lbcnn.lbc_unet import SkinnySmallUNetLBP, UNetLBP

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import optim
from tqdm import tqdm
from src.eval.eval_unet import eval_net
from src.models.unet.unet_model import UNet, SmallUNet, SkinnySmallUNet
from src.datasets.ice import BasicDatasetIce, Ice
from torch.utils.data import DataLoader
import wandb




def get_args():
    parser = argparse.ArgumentParser(description='Train AxialUnet on images and target masks',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--data_directory', metavar='D', type=str, default='/home/dsola/repos/PGA-Net/data/',
                        help='Directory where images, masks, and txt files reside.', dest='data_dir')
    parser.add_argument('-e', '--epochs', metavar='E', type=int, default=80,
                        help='Number of epochs', dest='epochs')
    parser.add_argument('-b', '--batch-size', metavar='B', type=int, nargs='?', default=1,
                        help='Batch size', dest='batchsize')
    parser.add_argument('-l', '--learning-rate', metavar='LR', type=float, nargs='?', default=0.0001,
                        help='Learning rate', dest='lr')
    parser.add_argument('-f', '--load', dest='load', type=str, default=False,
                        help='Load model from a .pth file')
    parser.add_argument('-s', '--scale', dest='scale', type=float, default=0.35,
                        help='Downscaling factor of the images')
    parser.add_argument('-c', '--crop', dest='crop', type=int, default=320,
                        help='Height and width of images and masks.')
    parser.add_argument('-sp', '--sparsity', dest='sparsity', type=float, default=80,
                        help='Sparsity of LBP filters.')
    parser.add_argument('-m', '--model', dest='model', type=str, default='unet',
                        help='Model to use.')
    parser.add_argument('-w', '--wandbname', dest='wandbname', type=str, default='tmp',
                        help='WandB name.')
    parser.add_argument('-i', '--imgdir', dest='imgdir', type=str, default='imgs',
                        help='Image directory.')

    return parser.parse_args()


def train_net(net, data_dir, device, epochs=20, batch_size=1, lr=0.0001, save_cp=True, img_scale=0.35, img_crop=320, img_dir='imgs'):
    train_set = Ice(os.path.join(data_dir, img_dir), os.path.join(data_dir, 'masks'),
                    os.path.join(data_dir, 'txt_files'), 'train_orig', img_scale, img_crop)
    val_set = Ice(os.path.join(data_dir, 'imgs'), os.path.join(data_dir, 'masks'),
                  os.path.join(data_dir, 'txt_files'), 'val_orig', img_scale, 256)

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=batch_size)

    global_step = 0

    optimizer = optim.RMSprop(net.parameters(), lr=lr, weight_decay=1e-8, momentum=0.9)
    # scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min' if net.n_classes > 1 else 'max', patience=2)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(epochs):
        net.train()
        epoch_loss = 0
        with tqdm(total=len(train_set), desc=f'Epoch {epoch + 1}/{epochs}', unit='img') as pbar:
            for batch in train_loader:
                imgs = batch['image']
                true_masks = batch['mask']

                imgs = imgs.to(device=device, dtype=torch.float32)
                target = true_masks.to(device=device, dtype=torch.long)

                if 'mobile' in args.model:
                    masks_pred = net(imgs)['out']
                else:
                    masks_pred = net(imgs)

                probs = F.softmax(masks_pred, dim=1)
                argmx = torch.argmax(probs, dim=1).to(dtype=torch.float32)

                example_images = [wandb.Image(imgs[0], caption='Image'),
                                  wandb.Image(target.to(dtype=torch.float)[0],
                                              caption='True Mask'),
                                  wandb.Image(argmx[0],
                                              caption='Predicted Mask')]

                wandb.log({"Examples": example_images})

                loss = criterion(masks_pred, target.squeeze(1))
                wandb.log({"Training Loss": loss})
                epoch_loss += loss.item()

                pbar.set_postfix(**{'loss (batch)': loss.item()})

                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_value_(net.parameters(), 0.1)
                optimizer.step()

                pbar.update(imgs.shape[0])
                global_step += 1
                if len(train_set) > 10:
                    n = 10
                else:
                    n = 1
                if global_step % (len(train_set) // (n * batch_size)) == 0:
                    if 'mobile' in args.model:
                        val_loss, val_iou, val_acc = eval_net(net, val_loader, device, mobile=True)
                    else:
                        val_loss, val_iou, val_acc = eval_net(net, val_loader, device)
                    wandb.log({"Validation Loss": val_loss})
                    wandb.log({"Validation IoU": val_iou})
                    wandb.log({"Validation Accuracy": val_acc})
                    # scheduler.step(val_loss)

        if save_cp:
            try:
                os.mkdir('../checkpoints/')
            except OSError:
                pass
            torch.save(net.state_dict(),
                       '../checkpoints/' + f'epoch{epoch + 1}.pth')


if __name__ == '__main__':
    args = get_args()
    wandb.init(name=args.wandbname)
    sparsity = args.sparsity / 100
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    if args.model == 'unet':
        net = UNet(n_channels=3, n_classes=3, bilinear=True)
    elif args.model == 'dsc_lbc_unet':
        net = DSCUNetLBP(3, 3)
    elif args.model == 'lbc_unet':
        net = UNetLBP(3, 3)
    elif args.model == 'dsc_unet':
        net = UNetDSC(n_channels=3, n_classes=3, bilinear=True)
    elif args.model == 'small_unet':
        net = SkinnySmallUNet(3, 3)
    elif args.model == 'small_dsc_unet':
        net = SkinnySmallUNetDSC(n_channels=3, n_classes=3, bilinear=True)
    elif args.model == 'small_lbc_unet':
        net = SkinnySmallUNetLBP(3, 3)
    elif args.model == 'small_dsc_lbc_unet':
        net = SkinnyDSCSmallUNetLBP(3, 3, sparsity=sparsity)
    elif args.model == 'deeplab_mobile_net':
        net = deeplabv3_mobilenet_v3_large(num_classes=3)
    elif args.model == 'lraspp_mobile_net':
        net = lraspp_mobilenet_v3_large(num_classes=3)
    else:
        raise ValueError('Please enter a valid model name.')


    wandb.watch(net)

    if args.load:
        net.load_state_dict(torch.load(args.load, map_location=device))

    net.to(device=device)

    try:
        if 'mobile' in args.model:
            crop = 256
        else:
            crop = args.crop
        train_net(net=net, data_dir=args.data_dir, epochs=args.epochs, batch_size=args.batchsize, lr=args.lr,
                  device=device,
                  img_scale=args.scale, img_crop=crop, img_dir=args.imgdir)
    except KeyboardInterrupt:
        torch.save(net.state_dict(), '../INTERRUPTED.pth')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
