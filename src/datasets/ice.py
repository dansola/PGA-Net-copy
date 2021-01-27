import os
import cv2
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from torch.utils.data import Dataset
from torchvision.transforms import transforms
import torch
import skimage.transform

MEANS = [121.4836, 122.35021, 122.517166]
STDS = [58.89167, 58.966404, 59.09349]


class Ice(Dataset):
    def __init__(self, imgs_dir, masks_dir, txt_dir, split, scale=1, crop=300):
        self.imgs_dir = imgs_dir
        self.masks_dir = masks_dir
        self.txt_dir = txt_dir
        self.split = split
        self.scale = scale
        self.crop = crop
        assert 0 < scale <= 1, 'Scale must be between 0 and 1'

        if split == "train":
            file_name = os.path.join(self.txt_dir, 'ice_train.txt')
        elif split == "val":
            file_name = os.path.join(self.txt_dir, 'ice_val.txt')
        elif split == "test":
            file_name = os.path.join(self.txt_dir, 'ice_test.txt')
        else:
            raise TypeError(f"Please enter one of train, val, or test for split.  You entered {split}.")

        self.img_ids = [i_id.strip() for i_id in open(file_name)]
        self.files = []
        for name in self.img_ids:
            img_file = os.path.join(imgs_dir, name)
            mask_file = os.path.join(masks_dir, name)
            self.files.append({
                "img": img_file,
                "mask": mask_file
            })

    def __len__(self):
        return len(self.files)

    def resize(self, pil_img):
        h, w = pil_img.size
        newW, newH = np.round_(self.scale * w), np.round_(self.scale * h)
        assert newW > 0 and newH > 0, 'Scale is too small'
        img_nd = np.array(pil_img)
        img_nd = skimage.transform.resize(img_nd,
                                          (newW, newH),
                                          mode='edge',
                                          anti_aliasing=False,
                                          anti_aliasing_sigma=None,
                                          preserve_range=True,
                                          order=0)
        if len(img_nd.shape) == 2:
            img_nd = np.expand_dims(img_nd, axis=2)

        return img_nd

    def process(self, img, mask):
        # img = cv2.resize(img, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_LINEAR)
        # mask = cv2.resize(mask, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_LINEAR)
        img = self.resize(img)
        mask = self.resize(mask)

        img = transforms.CenterCrop(self.crop)(Image.fromarray(img.astype(np.uint8)))
        mask = transforms.CenterCrop(self.crop)(Image.fromarray(mask.squeeze(-1).astype(np.uint8)))

        img = transforms.ToTensor()(img)
        img = transforms.Normalize(mean=MEANS, std=STDS)(img)
        img = img.permute(1, 2, 0).contiguous()

        mask = torch.tensor(np.array(mask))

        return img, mask

    def __getitem__(self, i):
        datafiles = self.files[i]
        img = Image.open(datafiles["img"])
        # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        mask = Image.open(datafiles["mask"])
        # mask = np.array(mask)[:, :, 0]
        # mask_new = np.zeros_like(mask[:, :, 0])
        # mask_new[(mask[:, :, 0] == 128)] = 1
        # mask_new[(mask[:, :, 0] == 255)] = 2
        # masks = [mask_new for _ in range(3)]
        # mask = np.stack(masks, axis=-1).astype('float')

        assert img.size == mask.size, \
            f'Image and mask {i} should be the same size, but are {img.size} and {mask.size}'

        img, mask = self.process(img, mask)
        mask = mask.unsqueeze(0)

        return {
            'image': img,
            'mask': mask
        }
