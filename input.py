import csv
import tensorflow as tf


# The side of the reshaped example (SIDExSIDE)
SIDE = 180
# The depth of the example
DEPTH = 3

# Global constants describing the cropped pascale data set.
NUM_CLASSES = 20
NUM_EXAMPLES_PER_EPOCH_FOR_TRAIN = 23758
NUM_EXAMPLES_PER_EPOCH_FOR_EVAL = 11918


def read_cropped_pascal(queue):
    """ Reads and parses files from the queue.
    Args:
        queue: A queue of strings in the format: file, widht, height, label

    Returns:
        An object representing a single example, with the following fields:
        key: a scalar string Tensor describing the filename & record number for this example.
        label: a tensor string with the label
        image: a [SIDE; SIDE, DEPTH] float32 tensor with the image data, resized with nn interpolation
    """

    class PASCALCroppedRecord(object):
        pass

    result = PASCALCroppedRecord()

    # Reader for text lines
    reader = tf.TextLineReader()

    # read a record from the queue
    result.key, value = reader.read(queue)

    # file,width,height,label
    record_defaults = [[""], [0], [0], [""]]

    image_path, _, _, result.label = tf.decode_csv(value, record_defaults)
    image = tf.image.decode_jpeg(image_path, channels=DEPTH)

    #reshape to a 4-d tensor
    image = tf.reshape(image,
                       [1, image.get_shape()[0].value,
                        image.get_shape()[1].value, image.get_shape()[2].value])

    # now image is 4-D float32 tensor: [1,SIDE,SIDE, DEPTH]
    image = tf.image.resize_nearest_neighbor(image, [SIDE, SIDE])
    # remove the 1st dimension -> [SIDE, SIDE, DEPTH]
    result.image = tf.squeeze(image)

    return result


def _image_and_label_batch(image, label, min_queue_examples, batch_size,
                           shuffle):
    """Construct a queued batch of images and labels.
    Args:
      image: 3-D Tensor of [SIDE, SIDE, DEPTH] of type.float32.
      label: 1-D Tensor of type string
      min_queue_examples: int32, minimum number of samples to retain
        in the queue that provides of batches of examples.
    batch_size: Number of images per batch.
    shuffle: boolean indicating whether to use a shuffling queue.
    Returns:
    images: Images. 4D tensor of [batch_size, SIDE, SIDE, DEPTH] size.
    labels: Labels. 1D tensor of [batch_size] size.
    """

    # Create a queue that shuffles the examples, and then
    # read 'batch_size' images + labels from the example queue.
    num_preprocess_threads = 16
    if shuffle:
        images, label_batch = tf.train.shuffle_batch(
            [image, label],
            batch_size=batch_size,
            num_threads=num_preprocess_threads,
            capacity=min_queue_examples + 3 * batch_size,
            min_after_dequeue=min_queue_examples)
    else:
        images, label_batch = tf.train.batch(
            [image, label],
            batch_size=batch_size,
            num_threads=num_preprocess_threads,
            capacity=min_queue_examples + 3 * batch_size)

    # Display the training images in the visualizer.
    tf.image_summary('images', images)

    return images, tf.reshape(label_batch, [batch_size])


def train_inputs(csv_path, batch_size):
    with open(csv_path + '/train.csv', 'r') as csv_file:
        # use dictreader to skip header line
        reader = csv.DictReader(csv_file)
        filenames = [
            ','.join([row["file"], row["width"], row["heigth"], row["label"]])
            for row in reader
        ]

    # prepend absolute path
    filenames = [csv_path + '/' + line for line in filenames]

    # Create a queue that produces the filenames (and other atrributes) to read
    queue = tf.train.string_input_producer(filenames)

    # Read examples from the queue
    record = read_cropped_pascal(queue)

    # Apply random distortions to the image
    distorted_image = tf.image.random_flip_left_right(record.image)
    distorted_image = tf.image.random_brightness(distorted_image, max_delta=63)
    distorted_image = tf.image.random_contrast(
        distorted_image, lower=0.2, upper=1.8)

    # Subtract off the mean and divide by the variance of the pixels.
    float_image = tf.image.per_image_whitening(distorted_image)

    # Ensure that the random shuffling has good mixing properties.
    min_fraction_of_examples_in_queue = 0.4
    min_queue_examples = int(NUM_EXAMPLES_PER_EPOCH_FOR_TRAIN *
                             min_fraction_of_examples_in_queue)

    print(
        'Filling queue with {} pascal cropped images before starting to train. '
        'This will take a few minutes.'.format(min_queue_examples))
    return _image_and_label_batch(float_image,
                                  record.label,
                                  min_queue_examples,
                                  batch_size,
                                  shuffle=True)


def validation_inputs(csv_path, batch_size):
    """Returns a batch of images from the validation dataset

    Args:
        csv_path: path of the cropped pascal dataset
        batch_size: Number of images per batch.
    Returns:
        images: Images. 4D tensor of [batch_size, SIDE, SIDE, DEPTH size.
        labes: Labels. 1D tensor of [batch_size] size.
    """

    with open(csv_path + '/validation.csv', 'r') as csv_file:
        # use dictreader to skip header line
        reader = csv.DictReader(csv_file)
        filenames = [
            ','.join([row["file"], row["width"], row["heigth"], row["label"]])
            for row in reader
        ]

    # prepend absolute path
    filenames = [csv_path + '/' + line for line in filenames]

    num_examples_per_epoch = NUM_EXAMPLES_PER_EPOCH_FOR_EVAL

    # Create a queue that produces the filenames to read.
    queue = tf.train.string_input_producer(filenames)

    # Read examples from files in the filename queue.
    record = read_cropped_pascal(queue)

    # Subtract off the mean and divide by the variance of the pixels.
    float_image = tf.image.per_image_whitening(record.image)

    # Ensure that the random shuffling has good mixing properties.
    min_fraction_of_examples_in_queue = 0.4
    min_queue_examples = int(num_examples_per_epoch *
                             min_fraction_of_examples_in_queue)

    # Generate a batch of images and labels by building up a queue of examples.
    return _image_and_label_batch(float_image,
                                  record.label,
                                  min_queue_examples,
                                  batch_size,
                                  shuffle=False)