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


class BasicDatasetIce(Dataset):
    def __init__(self, imgs_dir, masks_dir, txt_dir, split, scale=1, mask_suffix='', preprocessing=None, augmentation=None):
        self.imgs_dir = imgs_dir
        self.masks_dir = masks_dir
        self.txt_dir = txt_dir
        self.split = split
        self.scale = scale
        self.mask_suffix = mask_suffix
        self.preprocessing = preprocessing
        self.augmentation = augmentation
        assert 0 < scale <= 1, 'Scale must be between 0 and 1'

        if split == "train":
            fname = os.path.join(self.txt_dir, 'ice_train.txt')

        elif split == "val":
            fname = os.path.join(self.txt_dir, 'ice_val.txt')

        elif split == "test":
            fname = os.path.join(self.txt_dir, 'ice_test.txt')

        self.img_ids = [i_id.strip() for i_id in open(fname)]
        self.files = []
        for name in self.img_ids:
            img_file = os.path.join(imgs_dir, name)
            mask_file = os.path.join(masks_dir, name)
            self.files.append({
                "img": img_file,
                "mask": mask_file,
                "name": name
            })

    def __len__(self):
        return len(self.files)

    @classmethod
    def preprocess(cls, pil_img, scale, is_img=True):
        h, w = pil_img.size
        newW, newH = np.round_(scale * w), np.round_(scale * h)
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

        # HWC to CHW
        img_trans = img_nd.transpose((2, 0, 1))
        if is_img:
            if img_trans.max() > 1:
                img_trans = img_trans / 255
        # else:
        #    img_trans = rgb2gray(img_trans.transpose((1, 2, 0)))

        return img_trans

    def __getitem__(self, i):
        datafiles = self.files[i]
        # print('before')
        if self.augmentation:
            # print('after 1')
            img = cv2.imread(datafiles["img"])
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            mask = Image.open(datafiles["mask"])
            mask = np.array(mask)
            # print(datafiles["mask"])
            # print(mask.shape)
            # print(np.unique(mask))

            # extract certain classes from mask (e.g. cars)
            masks = [(mask == v) for v in [0, 1, 2]]
            mask = np.stack(masks, axis=-1).astype('float')
            # print(mask.shape)
        else:
            # print('after 2')
            img = Image.open(datafiles["img"])
            mask = Image.open(datafiles["mask"])

        # print(img.size, mask.size)
        assert img.size == mask.size, \
            f'Image and mask {i} should be the same size, but are {img.size} and {mask.size}'

        # img = self.preprocess(img, self.scale)
        # mask = self.preprocess(mask, self.scale, is_img=False)

        if self.augmentation:
            sample = self.augmentation(image=img, mask=mask)
            img, mask = sample['image'], sample['mask']
        else:
            img = self.preprocess(img, self.scale)
            mask = self.preprocess(mask, self.scale, is_img=False)
            # print('after process')
            # print(img.shape, mask.shape)

        if self.preprocessing:
            sample = self.preprocessing(image=img, mask=mask)
            img, mask = sample['image'], sample['mask']

            return torch.from_numpy(img).type(torch.FloatTensor), torch.from_numpy(mask).type(torch.FloatTensor)
        else:

            # plt.imshow(mask.transpose(1, 2, 0))
            # plt.title('dataloader')
            # plt.show()


            return {
                'image': torch.from_numpy(img).type(torch.FloatTensor),
                'mask': torch.from_numpy(mask).type(torch.FloatTensor)
            }


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
        img = img.permute(2, 0, 1).contiguous()

        return {
            'image': img,
            'mask': mask
        }


class IceWithProposals(Dataset):
    def __init__(self, imgs_dir, masks_dir, txt_dir, prop_dir, split, scale=1, crop=300):
        self.imgs_dir = imgs_dir
        self.masks_dir = masks_dir
        self.txt_dir = txt_dir
        self.prop_dir = prop_dir
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
            prop_file = os.path.join(prop_dir, name.replace('.tif', '.npy'))
            self.files.append({
                "img": img_file,
                "mask": mask_file,
                "prop": prop_file
            })

    def __len__(self):
        return len(self.files)

    def resize(self, pil_img, is_prop=False):
        h, w = (pil_img.shape[0], pil_img.shape[1]) if is_prop else pil_img.size
        frac = self.scale/0.5 if is_prop else self.scale
        newW, newH = np.round_(frac * w), np.round_(frac * h)
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

    def process(self, img, mask, prop):
        img = self.resize(img)
        mask = self.resize(mask)
        prop = self.resize(prop, is_prop=True)

        img = transforms.CenterCrop(self.crop)(Image.fromarray(img.astype(np.uint8)))
        mask = transforms.CenterCrop(self.crop)(Image.fromarray(mask.squeeze(-1).astype(np.uint8)))
        prop = transforms.CenterCrop(self.crop)(Image.fromarray(prop.squeeze(-1).astype(np.uint8)))

        img = transforms.ToTensor()(img)
        img = transforms.Normalize(mean=MEANS, std=STDS)(img)
        img = img.permute(1, 2, 0).contiguous()

        mask = torch.tensor(np.array(mask))
        prop = torch.tensor(np.array(prop))

        return img, mask, prop

    def __getitem__(self, i):
        datafiles = self.files[i]
        img = Image.open(datafiles["img"])
        mask = Image.open(datafiles["mask"])
        prop = np.load(datafiles["prop"])

        assert img.size == mask.size, \
            f'Image and mask {i} should be the same size, but are {img.size} and {mask.size}'

        img, mask, prop = self.process(img, mask, prop)

        assert mask.shape == prop.shape, \
            f'Mask and proposal {i} should be the same size, but are {img.shape} and {prop.shape}'

        mask = mask.unsqueeze(0)
        prop = prop.unsqueeze(0)
        img = img.permute(2, 0, 1).contiguous()

        return {
            'image': img,
            'mask': mask,
            'prop': prop
        }
