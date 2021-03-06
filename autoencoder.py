import pathlib

import torch
from torch.utils.data import Dataset
import argparse

from src import settings
from src.models.dataset import AudioEncoderDataset, find_largest_waveform_size
from src.models.generic_model import GeneralPerceptron, train_loop, test_loop


device = 'cuda' if torch.cuda.is_available() and settings.enable_gpu else 'cpu'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Model Trainer for Phoneme Generation')
    parser.add_argument('tsv_file', type=pathlib.Path, help='The TSV file to train from')
    parser.add_argument('clip_dir', type=pathlib.Path, help='The location of the .wav files')
    parser.add_argument('phoneme_dir', type=pathlib.Path,
                        help='The location of the subdirectories of the phoneme clips')
    parser.add_argument('--layer_count', type=int, default=1, help='Number of layers to use in the MLP')
    parser.add_argument('--layer_size', type=int, default=3000,
                        help='Number of neurons in the layers to use in the MLP')
    parser.add_argument('--learning_rate', type=float, default=0.01, help='The learning rate')
    parser.add_argument('--batch_size', type=int, default=32, help='The batch size for the data loader')
    parser.add_argument('--epochs', type=int, default=10, help='The number of epochs for training')
    parser.add_argument('--wave_size', type=int, default=-1,
                        help='The output size of the waveform, for if you\'ve ran this before.')
    parser.add_argument('--output', type=pathlib.Path, default=pathlib.Path('./encoder_model.sav'),
                        help='The file that you would like to save your model in')

    args = parser.parse_args()
    print('Running on {}'.format(device))

    # Determine the largest waveform size
    if args.wave_size < 0:
        max_output_size = find_largest_waveform_size(args.phoneme_dir)
    else:
        max_output_size = args.wave_size

    print('The largest waveform size is {}'.format(max_output_size))

    dataset = AudioEncoderDataset(args.tsv_file, args.clip_dir, args.phoneme_dir, max_output_size)

    # Version 1 (No Gradient Boosting)
    if not args.output.exists():
        model = GeneralPerceptron(max_output_size, max_output_size,
                                  args.layer_count,
                                  [args.layer_size] * args.layer_count,
                                  False).to(device)
    else:
        model = torch.load(args.output, map_location=device)['model']

    # Version 2 (Gradient Boosting)
    # model = GradientBoostingClassifier(model, 10, cuda=torch.cuda.is_available())
    # model.set_optimizer('SGD', lr=0.0001)
    criterion = torch.nn.MSELoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=args.learning_rate)

    loss = train_loop(torch.utils.data.DataLoader(dataset, batch_size=args.batch_size),  # , pin_memory=True),
                      model, criterion, optimizer)
    i = 0
    while abs(loss) > 10 and i < args.epochs:
        print('{}x{}: Training iteration {}, Loss {}\n'.format(args.layer_count, args.layer_size, i, loss))
        loss = train_loop(torch.utils.data.DataLoader(dataset, batch_size=args.batch_size),  # pin_memory=True),
                          model, criterion, optimizer)
        print('Training Error: {}'.format(loss))
        i += 1

    print(test_loop(torch.utils.data.DataLoader(dataset, batch_size=args.batch_size),  # pin_memory=True),
                    model, criterion))

    torch.save({'model': model, 'encoder': dataset.enc}, args.output)
