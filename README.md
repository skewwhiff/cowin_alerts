## Cowin Vaccine Slot Checker

For a given district name (or regex), this script will ping [Arogya Setu APIs](https://apisetu.gov.in/public/marketplace/api/cowin/cowin-public-v2#/) to determine slot availability for 18+ year olds in India, and send an email to people who want this info. Use `Python 3.8+` in any *Nix flavoured environment.

To get started, clone this repo and run  `pip install -r requirements.txt`. Start with `python check_vaccine_slots.py -h` to determine the options you need. 
Sample config file format: 
```json
{
  "creds": {
          "prod_creds": {
                  "<Same format as test creds>"
          }, "test_creds": {
                  "username": "testmail@no-reply.com",
                  "password": "",
                  "server": "localhost",
                  "port": "<port number as integer>"
          }
  },
  "cfg": [
    {
      "state": "<lowercase state name>",
      "districts": [
        {
          "district": "<lower case district name or regex>",
          "receivers": [
            "<email id>"
          ]
        }
      ]
    }
  ]
}
``` 

**NOTE: There won't be much updates in this repo. Feel free to fork and modify it as needed**
