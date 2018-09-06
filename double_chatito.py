"""
Double processes .chatito files for rasa

"""
import os
import re
from uuid import uuid4
import json
import shutil
import sys


if len(sys.argv) != 3:
    print("Usage: python {} <chatito_dir> <target dir>".format(sys.argv[0]))
    exit()

src_dir = sys.argv[1]
data_dir = sys.argv[2]



# create temp dir
tmp_dir = ".tmp" + uuid4().hex[:5]
final_ch_dir = uuid4().hex[:5]
json_dir = os.path.join(tmp_dir, "json")

os.makedirs(tmp_dir, exist_ok=True)
os.makedirs(final_ch_dir , exist_ok=True)
os.makedirs(json_dir , exist_ok=True)
os.makedirs(data_dir , exist_ok=True)

# process once with output to temp dir


def chatito2temp(src_path, target_path):
    # copies the file, but sets all samples to be train samples
    intent_definition = None
    slots = ""
    after_toplevel = False
    with open(src_path, "r") as src:
        with open(target_path, "w") as target:
            for line in src.readlines():
                if re.match("%.*", line):
                    if intent_definition is not None:
                        raise Exception("double_chatito can only handle one intent per file")
                    intent_definition = line
                match = re.match(
                    "%\[(?P<intent>.*)\]\('training': '(?P<train>[0-9]+)', 'testing': '(?P<test>[0-9]+)'\)", line)
                if match:
                    # change the number of train samples
                    intent, train, test = match.group('intent'), match.group('train'), match.group('test')
                    target.write(
                        "%[{}]('training': '{}')\n".format(intent, int(train)+int(test))
                    )

                else:
                    target.write(line)
                    if re.match("^    .*", line) is None:
                        if re.match("^@.*", line) is not None:
                            after_toplevel = True
                            slots += "\n"
                    if after_toplevel:
                        slots += line
    return intent_definition, slots


def run_chatito(file, json_path):
    os.makedirs(json_path)
    os.system("npx chatito {} --format=rasa --outputPath={}".format(file, json_path))


def data2chatito(json_path, target_path, from_original):
    intent_definition, slots = from_original
    with open(json_path, "r") as f:
        data = json.load(f)["rasa_nlu_data"]["common_examples"]

    with open(target_path, "w") as target:
        target.write(intent_definition)
        for example in data:
            target.write("    {}\n".format(example["text"]))

        target.write("\n"+slots)



def base2final(base_chatito, original_name, from_original):
    # run it, save it to a temp .json file, generate new chatito
    json_path = os.path.join(json_dir, original_name)
    target_path = os.path.join(final_ch_dir, original_name)
    run_chatito(base_chatito,json_path)
    data2chatito(os.path.join(json_path, "rasa_dataset_training.json"), target_path, from_original)



def deep_copy(src_dir, target_dir=tmp_dir):
    for file in os.listdir(src_dir):
        if os.path.isdir(file):
            deep_copy(os.path.join(src_dir, file), os.path.join(target_dir, file))
        elif re.match('.*\.chatito$', file):
            os.makedirs(target_dir, exist_ok=True)
            base_chatito = os.path.join(target_dir, file)
            from_original = chatito2temp(os.path.join(src_dir, file), base_chatito)
            base2final(base_chatito, file, from_original)


def run_chatito_dir(src_dir):
    os.system("npx chatito {} --format=rasa --outputPath={}".format(src_dir, data_dir))

deep_copy(src_dir)
run_chatito_dir(final_ch_dir)

# read output and generate new chatito files
# - copies all slot definitions
# - generates one top level definition of the intent with all train examples

# delete tmp dir
shutil.rmtree(tmp_dir)
shutil.rmtree(final_ch_dir)