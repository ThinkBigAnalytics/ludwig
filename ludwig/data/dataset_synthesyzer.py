#! /usr/bin/env python
# coding=utf-8
# Copyright (c) 2019 Uber Technologies, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
import argparse
import csv
import random
import string
import uuid
import os

import numpy as np

import yaml

from ludwig.utils.misc import get_from_registry
from skimage.io import imsave

letters = string.ascii_letters


def generate_string(length):
    sequence = []
    for _ in range(length):
        sequence.append(random.choice(letters))
    return ''.join(sequence)


def build_vocab(size):
    vocab = []
    for _ in range(size):
        vocab.append(generate_string(random.randint(2, 10)))
    return vocab


def return_none(feature):
    return None


def assign_vocab(feature):
    feature['idx2str'] = build_vocab(feature['vocab_size'])


def build_feature_parameters(features):
    feature_parameters = {}
    for feature in features:
        fearure_builder_function = get_from_registry(
            feature['type'],
            parameters_builders_registry
        )

        feature_parameters[feature['name']] = fearure_builder_function(feature)
    return feature_parameters


parameters_builders_registry = {
    'category': assign_vocab,
    'text': assign_vocab,
    'numerical': return_none,
    'binary': return_none,
    'set': assign_vocab,
    'bag': assign_vocab,
    'sequence': assign_vocab,
    'timeseries': return_none,
    'image': return_none
}


def build_synthetic_dataset(dataset_size, features):
    build_feature_parameters(features)
    header = []
    for feature in features:
        header.append(feature['name'])

    yield header
    for _ in range(dataset_size):
        yield generate_datapoint(features)


def generate_datapoint(features):
    datapoint = []
    for feature in features:
        if ('cycle' in feature and feature['cycle'] == True and
                feature['type'] in cyclers_registry):
            cycler_function = cyclers_registry[feature['type']]
            feature_value = cycler_function(feature)
        else:
            generator_function = get_from_registry(
                feature['type'],
                generators_registry
            )
            feature_value = generator_function(feature)
        datapoint.append(feature_value)
    return datapoint


def generate_category(feature):
    return random.choice(feature['idx2str'])


def generate_text(feature):
    text = []
    for _ in range(random.randint(feature['max_len'] -
                                  int(feature['max_len'] * 0.2),
                                  feature['max_len'])):
        text.append(random.choice(feature['idx2str']))
    return ' '.join(text)


def generate_numerical(feature):
    return random.uniform(
        feature['min'] if 'min' in feature else 0,
        feature['max'] if 'max' in feature else 1
    )


def generate_binary(feature):
    return random.choice([True, False])


def generate_sequence(feature):
    length = feature['max_len']
    if 'min_len' in feature:
        length = random.randint(feature['min_len'], feature['max_len'])

    sequence = [random.choice(feature['idx2str']) for _ in range(length)]

    return ' '.join(sequence)


def generate_set(feature):
    elems = []
    for _ in range(random.randint(0, feature['max_len'])):
        elems.append(random.choice(feature['idx2str']))
    return ' '.join(list(set(elems)))


def generate_bag(feature):
    elems = []
    for _ in range(random.randint(0, feature['max_len'])):
        elems.append(random.choice(feature['idx2str']))
    return ' '.join(elems)


def generate_timeseries(feature):
    series = []
    for _ in range(feature['max_len']):
        series.append(
            str(
                random.uniform(
                    feature['min'] if 'min' in feature else 0,
                    feature['max'] if 'max' in feature else 1
                )
            )
        )
    return ' '.join(series)


def generate_image(feature):
    # Read num_channels, width, height
    num_channels = feature['num_channels']
    width = feature['width']
    height = feature['height']
    image_dest_folder = feature['destination_folder']

    if width <= 0 or height <= 0 or num_channels < 1:
        raise ValueError('Invalid arguments for generating images')

    # Create a Random Image
    if num_channels == 1:
        img = np.random.rand(width, height) * 255
    else:
        img = np.random.rand(width, height, num_channels) * 255.0

    # Generate a unique random filename
    image_filename = uuid.uuid4().hex[:10].upper() + '.jpg'

    # Save the image to disk either in a specified location/new folder
    try:
        if not os.path.exists(image_dest_folder):
            os.mkdir(image_dest_folder)

        image_dest_path = os.path.join(image_dest_folder, image_filename)
        imsave(image_dest_path, img.astype('uint8'))

    except IOError as e:
        raise IOError('Unable to create a folder for images/save image to disk.'
                      '{0}'.format(e))

    return image_dest_path


generators_registry = {
    'category': generate_category,
    'text': generate_sequence,
    'numerical': generate_numerical,
    'binary': generate_binary,
    'set': generate_set,
    'bag': generate_bag,
    'sequence': generate_sequence,
    'timeseries': generate_timeseries,
    'image': generate_image
}

category_cycle = 0


def cycle_category(feature):
    global category_cycle
    if category_cycle >= len(feature['idx2str']):
        category_cycle = 0
    category = feature['idx2str'][category_cycle]
    category_cycle += 1
    return category


binary_cycle = False


def cycle_binary(feature):
    global binary_cycle
    if binary_cycle:
        binary_cycle = False
        return True
    else:
        binary_cycle = True
        return False


cyclers_registry = {
    'category': cycle_category,
    'binary': cycle_binary
}


def write_csv(dataset, csv_file_path):
    with open(csv_file_path, 'w') as file:
        writer = csv.writer(file)
        for row in dataset:
            writer.writerow(row)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='This script generates a synthetic dataset.')
    parser.add_argument('csv_file_path', help='output csv file path')
    parser.add_argument(
        '-d',
        '--dataset_size',
        help='size of the dataset',
        type=int,
        default=100
    )
    parser.add_argument(
        '-f',
        '--features',
        default='[\
          {name: text_1, type: text, vocab_size: 20, max_len: 20}, \
          {name: text_2, type: text, vocab_size: 20, max_len: 20}, \
          {name: category_1, type: category, vocab_size: 10}, \
          {name: category_2, type: category, vocab_size: 15}, \
          {name: numerical_1, type: numerical}, \
          {name: numerical_2, type: numerical}, \
          {name: binary_1, type: binary}, \
          {name: binary_2, type: binary}, \
          {name: set_1, type: set, vocab_size: 20, max_len: 20}, \
          {name: set_2, type: set, vocab_size: 20, max_len: 20}, \
          {name: bag_1, type: bag, vocab_size: 20, max_len: 10}, \
          {name: bag_2, type: bag, vocab_size: 20, max_len: 10}, \
          {name: sequence_1, type: sequence, vocab_size: 20, max_len: 20}, \
          {name: sequence_2, type: sequence, vocab_size: 20, max_len: 20}, \
          {name: timeseries_1, type: timeseries, max_len: 20}, \
          {name: timeseries_2, type: timeseries, max_len: 20}, \
          ]',
        type=yaml.load, help='dataset features'
    )
    args = parser.parse_args()

    dataset = build_synthetic_dataset(args.dataset_size, args.features)
    write_csv(dataset, args.csv_file_path)