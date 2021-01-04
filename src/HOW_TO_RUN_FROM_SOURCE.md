If you want to use debbit on mac/Windows please download a release from https://github.com/jakehilborn/debbit/releases  
If you want to develop debbit or use on Linux follow instructions below.

# One time setup
1. Clone this GitHub repo or download the source code.
2. Install the latest version of Firefox.
3. Download the latest `geckodriver` for your OS from here https://github.com/mozilla/geckodriver/releases Then, extract the zip/tar.gz and place `geckodriver` (or `geckodriver.exe`) in the `debbit/src/program_files` directory, which is directly under the same folder as `debbit.py` is in.
    - Alternatively, if using macOS, you can `brew install geckodriver` and symlink it into this directory (`ln -s /usr/local/bin/geckodriver geckodriver`)
4. Copy and rename the file `sample_config.txt` to `config.txt` (or `config.yml`) in the same directory.
5. Configure your python3 environment and dependencies.

    These instructions will vary somewhat depending on your platform. For example,
    if your system already has Python3 then you'll use `pip` instead of `pip3`. If
    you don't have pip installed, search on Google for how to install pip.

    ```
    debbit/src
    pip3 install --user pipenv
    pip3 install --user --upgrade pipenv
    ```

# Routinely
When dependencies are updated, and on first-time setup, you'll need to run the following:

```
cd debbit/src
pipenv install
```

# Every Time: run debbit via pipenv

`pipenv run python debbit.py`

You can also use `pipenv shell` then `python debbit.py` if you want to keep the `pipenv` environment around. 
