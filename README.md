# imgconvert

Convert images matching a given list of types to another format.

Does not manipulate source files, only reads and then converts to another format into the `target_dir` in the `target_format`.

## How to use it

### Configuration

Config is read from `config.yaml`.

### Run it

```python
>>> config = read_config("config.yml")
>>> converter = Convert(source_dir=config.get("source_dir"),
                                 target_dir=config.get('target_dir'),
                                 target_format=config.get('target_format'),
                                 file_types=config.get("file_types"))
>>> converter.read_dir()
>>> converter.clean(verbose=True)
>>> converter.convert(verbose=True)
```
