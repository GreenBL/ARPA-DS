-- Droppare il database se esiste
DROP DATABASE IF EXISTS db;

-- Creare il nuovo database
CREATE DATABASE db;

-- Selezionare il nuovo database
USE db;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    surname VARCHAR(50) NOT NULL,
    phone_number VARCHAR(15) NOT NULL,
    date_birth DATE NOT NULL,
    gender ENUM('maschio', 'femmina', 'LGBTQ+') NOT NULL,
    email VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL 
);
