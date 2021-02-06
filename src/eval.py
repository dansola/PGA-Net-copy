import torch
import torch.nn.functional as F
from tqdm import tqdm
from metrics.segmentation import _fast_hist, per_class_pixel_accuracy, jaccard_index


def eval_net(net, loader, device):
    """Evaluation without the densecrf with the dice coefficient"""
    net.eval()
    n_val = len(loader)  # the number of batch
    tot_loss, tot_iou, tot_acc = 0, 0, 0

    with tqdm(total=n_val, desc='Validation round', unit='batch', leave=False) as pbar:
        for batch in loader:
            imgs, true_masks = batch['image'], batch['mask']
            props = batch['prop']

            props = props.to(device=device, dtype=torch.long)
            imgs = imgs.to(device=device, dtype=torch.float32)
            true_masks = true_masks.to(device=device, dtype=torch.long)

            with torch.no_grad():
                # mask_pred = net(imgs)
                mask_pred = net(imgs, props)

            argmx = torch.argmax(mask_pred, dim=1)
            hist = _fast_hist(true_masks.squeeze(0).squeeze(0), argmx.squeeze(0).to(dtype=torch.long), 3)

            tot_iou += jaccard_index(hist)[0]
            tot_acc += per_class_pixel_accuracy(hist)[0]
            tot_loss += F.cross_entropy(mask_pred, true_masks.squeeze(1)).item()
            pbar.update()

    net.train()
    return tot_loss / n_val, tot_iou / n_val, tot_acc / n_val
