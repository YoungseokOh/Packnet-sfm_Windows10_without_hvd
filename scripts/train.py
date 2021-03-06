# Copyright 2020 Toyota Research Institute.  All rights reserved.

import sys
sys.path.insert(0, 'C:/Users/seok436/PycharmProjects/Packnet-sfm_Windows10_without_hvd')

import argparse
import torch
import pytorch_qat.quantizer

from packnet_sfm.models.model_wrapper import ModelWrapper
from packnet_sfm.models.model_checkpoint import ModelCheckpoint
from packnet_sfm.trainers.horovod_trainer import HorovodTrainer
from packnet_sfm.utils.config import parse_train_file
from packnet_sfm.utils.load import set_debug, filter_args_create
# from packnet_sfm.utils.horovod import hvd_init, rank
from packnet_sfm.loggers import WandbLogger
from pytorch_qat import *
from pytorch_qat.cifar import fuse_ConvBNReLU


def parse_args():
    """Parse arguments for training script"""
    parser = argparse.ArgumentParser(description='PackNet-SfM training script')
    parser.add_argument('file', type=str, help='Input file (.ckpt or .yaml)')
    args = parser.parse_args()
    assert args.file.endswith(('.ckpt', '.yaml')), \
        'You need to provide a .ckpt of .yaml file'
    return args


def train(file):
    """
    Monocular depth estimation training script.

    Parameters
    ----------
    file : str
        Filepath, can be either a
        **.yaml** for a yacs configuration file or a
        **.ckpt** for a pre-trained checkpoint file.
    """
    # Initialize horovod
    # hvd_init()

    # Produce configuration and checkpoint from filename
    config, ckpt = parse_train_file(file)

    # Set debug if requested
    set_debug(config.debug)

    # Wandb Logger
    logger = None if config.wandb.dry_run \
        else filter_args_create(WandbLogger, config.wandb)

    # model checkpoint
    checkpoint = None if config.checkpoint.filepath == '' else \
        filter_args_create(ModelCheckpoint, config.checkpoint)

    # Initialize model wrapper
    model_wrapper = ModelWrapper(config, resume=ckpt, logger=logger)

    # Quantization
    if config.arch.quantization:
        depth_net = fuse_ConvBNReLU(model_wrapper.model.depth_net)
        model_wrapper.model.depth_net = pytorch_qat.quantizer.QuantizedModel(depth_net)
        quantization_config = torch.quantization.get_default_qconfig("fbgemm")
        model_wrapper.model.depth_net.qconfig = quantization_config
        print(model_wrapper.model.depth_net.qconfig)
        torch.quantization.prepare_qat(model_wrapper.model.depth_net, inplace=True)
        # quantized_model = torch.quantization.convert(model_wrapper.model.depth_net, inplace=True)
    # Create trainer with args.arch parameters
    trainer = HorovodTrainer(**config.arch, checkpoint=checkpoint)

    # Train model
    trainer.fit(model_wrapper)
    # # Jit save
    # depth_net = model_wrapper.model.depth_net
    # torch.quantization.prepare_qat(depth_net, inplace=True)
    # depth_net.to()
    # quantized_model = torch.quantization.convert(depth_net, inplace=True)
    # torch.jit.save(torch.jit.script(quantized_model), 'C:/Users/seok436/PycharmProjects/pytorch2onnx/encoder_qat.pth')
    # torch.jit.save(torch.jit.script(depth_net.decoder.decoder), 'C:/Users/seok436/PycharmProjects/pytorch2onnx/decoder_qat.pth')

if __name__ == '__main__':
    args = parse_args()
    train(args.file)
