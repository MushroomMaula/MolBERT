import logging
import pprint
from abc import ABC
from argparse import ArgumentParser, Namespace

import torch
from pytorch_lightning import Trainer, seed_everything
from pytorch_lightning.callbacks import LearningRateMonitor
from pytorch_lightning.callbacks import ModelCheckpoint
from pytorch_lightning.loggers import WandbLogger

from molbert.apps.args import get_default_parser
from molbert.models.base import MolbertModel

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class BaseMolbertApp(ABC):
    @staticmethod
    def load_model_weights(model: MolbertModel, checkpoint_file: str) -> MolbertModel:
        """
        PL `load_from_checkpoint` seems to fail to reload model weights. This function loads them manually.
        See: https://github.com/PyTorchLightning/pytorch-lightning/issues/525
        """
        logger.info(f'Loading model weights from {checkpoint_file}')
        checkpoint = torch.load(checkpoint_file, map_location=lambda storage, loc: storage)

        # load weights from checkpoint, strict=False allows to ignore some weights
        # e.g. weights of a head that was used during pretraining but isn't present during finetuning
        # and also allows to missing keys in the checkpoint, e.g. heads that are used for finetuning
        # but weren't present during pretraining
        model.load_state_dict(checkpoint['state_dict'], strict=False)
        return model

    def run(self, args=None):
        args = self.parse_args(args)
        seed_everything(args.seed)

        pprint.pprint('args')
        pprint.pprint(args.__dict__)
        pprint.pprint('*********************')

        checkpoint_callback = ModelCheckpoint(monitor='valid_loss', verbose=True, save_last=True)

        logger.info(args)

        lr_logger = LearningRateMonitor()

        trainer = Trainer(
            default_root_dir=args.default_root_dir,
            min_epochs=args.min_epochs,
            max_epochs=args.max_epochs,
            val_check_interval=args.val_check_interval,
            limit_val_batches=args.limit_val_batches,
            devices="auto" if args.gpus == 0 else args.gpus,
            strategy=args.strategy,
            precision=args.precision,
            num_nodes=args.num_nodes,
            accumulate_grad_batches=args.accumulate_grad_batches,
            fast_dev_run=args.fast_dev_run,
            callbacks=[lr_logger, checkpoint_callback],
            logger=WandbLogger() if args.wandb else None
        )

        model = self.get_model(args)
        logger.info(f'Start Training model {model}')

        logger.info('')
        trainer.fit(model, ckpt_path=args.resume_from_checkpoint)
        logger.info('Training loop finished.')

        return trainer

    def parse_args(self, args) -> Namespace:
        """
        Parse command line arguments
        """
        parser = get_default_parser()
        parser = self.add_parser_arguments(parser)
        return parser.parse_args(args=args)

    @staticmethod
    def get_model(args) -> MolbertModel:
        raise NotImplementedError

    @staticmethod
    def add_parser_arguments(parser: ArgumentParser) -> ArgumentParser:
        """
        Adds model specific options to the default parser
        """
        raise NotImplementedError
