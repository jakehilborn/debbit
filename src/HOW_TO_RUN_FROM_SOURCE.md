If you want to use debbit on mac/Windows please download a release from https://github.com/jakehilborn/debbit/releases
If you want to develop debbit or use on Linux follow instructions below.

# One time setup
1. Clone this GitHub repo or download the source code
1. Install the latest version of Firefox
1. Download the latest `geckodriver` for your OS from here https://github.com/mozilla/geckodriver/releases
    Extract the zip/tar.gz and place `geckodriver` (or `geckodriver.exe`) in the `debbit/src/program_files` directory, which is directly under the same folder as `debbit.py` is in.
    - If using Windows, you will need to rename `geckodriver.exe` to `geckodriver`
    - Alternatively, if using Mac, you can `brew install geckodriver` and symlink it into this directory (`ln -s /usr/local/bin/geckodriver geckodriver`)
1. Copy and rename the file `sample_config.txt` to `config.txt` (or `config.yml`) in the same directory
1. Configure your python3 environment and dependencies. All of the following commands must be run from the `debbit/src` directory.

    These instructions will vary somewhat depending on your platform. For example,
    if your system already has Python3 then you'll use `pip` instead of `pip3`. If
    you don't have pip installed, search on Google for how to install pip.

    ```
    # Install pipenv
    pip3 install --user pipenv
    pip3 install --user --upgrade pipenv
    ```

# Routinely
When dependencies are updated, and on first-time setup, you'll need to run the following:

```
# install dependencies listed in Pipfile
pipenv install
```

# Every Time: run debbit via pipenv

`pipenv run python debbit.py`

You can also use `pipenv shell` then `python debbit.py` if you want to keep the `pipenv` environment around. 
