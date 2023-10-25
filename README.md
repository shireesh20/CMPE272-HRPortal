# CMPE272-HRPortal

# Do the DB setup from the below link
Get data from <a href="https://github.com/datacharmer/test_db"> here... </a> and injest into ur local db </br>
<br/>
Create a table hr_user with below cmd:
<code>
CREATE TABLE hr_user (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    address VARCHAR(200),
    email VARCHAR(120) NOT NULL UNIQUE,
    mobile_number VARCHAR(20) NOT NULL UNIQUE,
    password_hash VARCHAR(128),
    role VARCHAR(255)
);
</code><br/> 
Configure app.config['SQLALCHEMY_DATABASE_URI'] with your local database connection string <br/><br/>
Install all required packages from requirements.txt

<code> python3 install -r requirements.txt </code>

To run the application: <code> Python3 main.py </code>
<hr/>

# Project-Details:






# High Level Design

![High-Level-Design](https://github.com/shireesh20/CMPE272-HRPortal/blob/main/static/assets/systemdesign.png)


# Database Design

![Database Design](https://github.com/shireesh20/CMPE272-HRPortal/blob/main/static/assets/dbdesign.png)





# UML Diagram

![UML_diagram](https://github.com/shireesh20/CMPE272-HRPortal/blob/main/static/assets/uml.png)

# Sequence Diagram

![sequence-diagram](https://github.com/shireesh20/CMPE272-HRPortal/blob/main/static/assets/sequence.png)

# application home

<img width="1440" alt="home-page" src="https://github.com/shireesh20/CMPE272-HRPortal/blob/main/static/assets2/home.png">










