import os
from pathlib import Path
from typing import List

import yaml
from PIL import Image
from tqdm import tqdm


class Convert:
    def __init__(self, source_dir: str, target_dir: str, target_format, file_types: list):
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.target_format = target_format
        self.file_types = file_types
        self.file_list: List[Path] = []

    @staticmethod
    def get_file_ext(file_name: str) -> str:
        return f".{file_name.split('.')[-1]}"

    def read_dir(self) -> List[Path]:
        """
        Read files in source_dir.

        :return:
        """
        print(f"Reading {self.source_dir}")
        path = Path(self.source_dir)
        self.file_list: List[Path] = [x for x in path.iterdir()]

        return self.file_list

    def clean(self, verbose=False) -> List[Path]:
        """
        Remove files that do not match files in file_list.

        :return: :class:`list[Path]`
        """

        clean_count: int = 0
        for idx, file in enumerate(self.file_list):
            if self.get_file_ext(file.name) not in self.file_types:
                if verbose:
                    print(f"Removed {str(self.file_list[idx]).split('/')[-1]}")
                self.file_list.pop(idx)
                clean_count += 1

        print(f"Removed {clean_count} files from the list.")

        return self.file_list

    def convert(self, verbose=False):
        """
        Convert files in the file list to the specified type and location.

        :param bool verbose:
        :return:
        """

        count = 0
        for file in tqdm(self.file_list, desc=f"Converting to {self.target_format}"):
            file_name, file_type = file.name.split('.')

            with Image.open(file) as pf:
                pf.save(f"{self.target_dir}/{file_name.lower()}.{self.target_format}")
                count += 1

        if verbose:
            print(f"\n{count} files written to {self.target_dir}.")

        return {"files_converted": count}


def read_config(config_file: str) -> dict:
    """
    Read config file.

    :param str config_file:
    :return:
    """
    with open(config_file, 'rb') as cf:
        parsed_config = yaml.safe_load(cf)

    parsed_config['HOME'] = os.getenv('HOME')

    return parsed_config


if __name__ == '__main__':
    config = read_config("config.yml")
    converter: Convert = Convert(source_dir=config.get("source_dir"),
                                 target_dir=config.get('target_dir'),
                                 target_format=config.get('target_format'),
                                 file_types=config.get("file_types"))
    converter.read_dir()
    converter.clean(verbose=True)
    converter.convert(verbose=True)
