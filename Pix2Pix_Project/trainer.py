"""Pix2Pix implementation based on 
https://github.com/junyanz/pytorch-CycleGAN-and-pix2pix
Developed by David Dória https://github.com/daversd for
2020-2021 B-pro Architectural Design RC4

"""

import torch
import torch.onnx
from torch.utils.tensorboard import SummaryWriter
import pix2pix_helpers.util as util
from pix2pix_helpers.create_dataset import ImageFolderLoader
from pix2pix_helpers.pix2pix_model import Pix2PixModel
from matplotlib import pyplot as plt
import time
import os

##
# High level setup
##

TRAIN = True            # Determines if the program must enter training mode
TEST = True             # Determines if the program must enter testing mode (loads the latest checkpoint)
TEST_SAMPLE = 5         # The number of samples for testing mode
WRITE_LOGS = True       # Determines if tensorboard logs should be written to disk
SAVE_CKPTS = True       # Determines if checkpoints should be saved
SAVE_IMG_CKPT = True    # Determines if images should be saved for each checkpoint
EXPORT_MODEL = True     # Determines if the model should be exported (loads the latest checkpoint)

MODEL_NAME = 'pix2pix_run_1'                            # The name of the model for this run
CKPT_DIR = os.path.join('checkpoints', MODEL_NAME)      # The folder to save checkpoints to
LOG_DIR = 'runs/' + MODEL_NAME                          # The folder to save tensorboard logs to
TEST_DIR = 'test/' + MODEL_NAME                         # The folder to save test images to

# Create the required folders
if SAVE_CKPTS:
    if not os.path.isdir(CKPT_DIR):
        os.makedirs(CKPT_DIR)

if WRITE_LOGS:
    if not os.path.isdir(LOG_DIR):
        os.makedirs(LOG_DIR)

if SAVE_IMG_CKPT:
    if not os.path.isdir(TEST_DIR):
        os.makedirs(TEST_DIR)

BATCH_SIZE = 1
EPOCHS = 10                 # Will be split in two parts, must be even

PRINT_FREQ = 100            # Interval of steps between print logs
LOG_FREQ = 100              # Interval of steps between tensorboard logs
CKPT_FREQ = 2               # Interval of epochs between checkpoints

# Initialize the log writer
if WRITE_LOGS:
    writer = SummaryWriter(log_dir=LOG_DIR)

DEVICE = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

##
# Main program
##

if __name__ == '__main__':
    if TRAIN:
        # Create the training data set
        trainData = ImageFolderLoader("facades/AB", phase='train')
        trainSet = torch.utils.data.DataLoader(trainData, batch_size=BATCH_SIZE, shuffle= False, num_workers=4)
        
        # Create the pix2pix model
        model = Pix2PixModel(CKPT_DIR, MODEL_NAME, is_train=True, n_epochs=EPOCHS/2, n_epochs_decay=EPOCHS/2)

        model.setup()
        total_iters = 0

        # Initiate the training iteration
        for epoch in range(EPOCHS):
            epoch_start_time = time.time()
            iter_data_time = time.time()
            epoch_iter = 0

            if epoch != 0:
                model.update_learning_rate()

            # Iterate through the data batches in the training set
            for i, data in enumerate(trainSet):
                iter_start_time = time.time()

                # Setup counters
                total_iters += BATCH_SIZE
                epoch_iter += BATCH_SIZE
                
                # Feed input through model, optimize parameters
                model.set_input(data)
                model.optimize_parameters()

                # Use this for logging losses in tensorboard
                if total_iters % PRINT_FREQ == 0:
                    losses = model.get_current_losses()
                    t_comp = (time.time() - iter_start_time) / BATCH_SIZE
                    print(f'Step {total_iters} | Epoch {epoch} | GAN Loss: {losses["G_GAN"]:.3f} | Gen. L1: {losses["G_L1"]:.3f} | Disc. real: {losses["D_real"]:.3f} | Disc. fake: {losses["D_fake"]:.3f}')

                # Use this to log to tensorboard
                if WRITE_LOGS and total_iters % LOG_FREQ == 0:
                    losses = model.get_current_losses().items()
                    for name, loss in losses:
                        writer.add_scalar(name, loss, total_iters) # type: ignore
                    writer.close() # type: ignore
            
                iter_data_time = time.time()

            # Save checkpoints per epochs
            if SAVE_CKPTS and epoch % CKPT_FREQ == 0:
                print('Saving the model at the end of epoch %d, iters %d' % (epoch, total_iters))
                model.save_network(epoch)

                # Save image per checkpoint
                if SAVE_IMG_CKPT:
                    print('Saving current epoch test to test folder')
                    visuals = model.get_current_visuals()
                    save_path = os.path.join(TEST_DIR, 'epoch_' + str(epoch) + '.jpg')
                    util.save_visuals(visuals, save_path)

            # Print details at the end of the epoch
            print('End of epoch %d / %d \t Time Taken: %d secs' % 
                (epoch, EPOCHS, time.time() - epoch_start_time))
            
    
        # Save / overwrite final epoch and image
        if SAVE_CKPTS:
            print('Saving the model at the end of training')
            model.save_network(epoch)

            if SAVE_IMG_CKPT:
                print('Saving final epoch test to test folder')
                visuals = model.get_current_visuals()
                save_path = os.path.join(TEST_DIR, 'epoch_' + str(epoch) + '.jpg')
                util.save_visuals(visuals, save_path)

        # Plot last visuals from the model once training is complete
        visuals = model.get_current_visuals()
        util.plot_visuals(visuals)
    
    if TEST:
        # Create the testing data set
        testData = ImageFolderLoader('facades/AB', phase='test', flip=False)
        testSet = torch.utils.data.DataLoader(testData, batch_size=BATCH_SIZE, shuffle= False, num_workers=0)

        # Create the pix2pix model in testing mode
        model = Pix2PixModel(CKPT_DIR, MODEL_NAME, is_train=False, n_epochs=EPOCHS/2, n_epochs_decay=EPOCHS/2)
        model.setup()
        model.eval()
        model.load_networks(0)

        # Iterate through test data set, for the lenght of the test sample
        for i, data in enumerate(testSet):
            if i < TEST_SAMPLE:
                model.set_input(data)
                model.test()
                visuals = model.get_current_visuals()
                save_path = os.path.join(TEST_DIR, 'test_' + str(i) + '.jpg')
                util.save_visuals(visuals, save_path)
            else:
                break
    
    if EXPORT_MODEL:
        # Create dummy input
        x = torch.randn(1, 3, 256, 256)

        # Create the model and load the latest checkpoint
        model = Pix2PixModel(CKPT_DIR, MODEL_NAME, is_train=False, n_epochs=EPOCHS/2, n_epochs_decay=EPOCHS/2)
        model.setup()
        model.eval()
        model.load_networks(0)

        if not os.path.isdir('exported'):
            os.makedirs('exported')
        
        path = os.path.join('exported', f'{MODEL_NAME}.onnx')
        f = open(path, 'w+')

        torch.onnx.export(model.netG, x.to(DEVICE), path, training=torch.onnx.TrainingMode.EVAL, export_params=True, opset_version=10)
