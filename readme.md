# **BROKER TERMINAL WITH EXCEL**
An excel based interface for Alice Blue broker. Users can use the application to connect alice blue api with excel, and then use it as an interface to perform operations like BUY, SELL, FUTURE BUY, FUTURE SELL, etc by writing excel formulas for various strategies. 

## **RUN USING EXE FILE**
It has support for only alice blue broker. Support for other brokers is under development. 

To run the application :
- Run the exe file on windows. Application will exit with no credentials found error. Empty template files will be created in broker directory for credentials. 
- Fill in the credentials for alice blue as values for the keys in the json credentials file and run the exe file again. 

## **RUN USING PYTHON SCRIPT**
- Setup a virtual environment

    ``python -m venv env``

- Install python dependencies

    ``python -m pip install -r requirements.txt``

- Run the main file

    ``python main.py``

- Setup broker credentials : Template files are created on running the *main.py* file for the first time. Fill in the broker credentials in the template file created in the broker directory. And run the *main.py* file again. 