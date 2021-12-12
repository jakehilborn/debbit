cd ..\..\src

pip install -U pip
pip list --outdated --format=freeze | %{$_.split('==')[0]} | %{pip install --upgrade $_}
pip install coverage==5.3.1 --force-reinstall

# TODO don't hardcode list of merchants
pyinstaller --clean -F -c debbit.py program_files\merchants\amazon_gift_card_reload.py program_files\merchants\att_bill_pay.py program_files\merchants\example_merchant.py program_files\merchants\optimum_bill_pay.py program_files\merchants\xfinity_bill_pay.py
Copy-Item dist\debbit.exe -Destination release\win64\debbit.exe

$REL_VERSION_TXT = Get-Content release\rel_version.txt | Out-String
$REL_VERSION=$REL_VERSION_TXT.Trim()
Compress-Archive -Path release\win64\* -DestinationPath release\debbit-$REL_VERSION-win64.zip -Force

pause
