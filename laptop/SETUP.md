# Laptop worker setup (about 30 minutes, once)

1. Install Python: open PowerShell and run  winget install -e --id Python.Python.3.12  then close PowerShell.
2. In Documents\Kairos\worker, copy env.template to a new file named .env and fill in the keystring and shared secret
   (etsy.com/developers > Your Apps > your app). Save. Never paste the keys into a chat.
3. In the same Etsy app page, add this callback URL:  http://localhost:3003/callback
4. Open PowerShell in Documents\Kairos\worker and run:  py kairos_worker.py login   (click "Allow access" in the browser)
5. Run:  py kairos_worker.py test   It should print your shop name.
6. Schedule it every 15 minutes:
   schtasks /Create /SC MINUTE /MO 15 /TN "Kairos worker" /TR "pyw \"%USERPROFILE%\Documents\Kairos\worker\kairos_worker.py\" once" /F
