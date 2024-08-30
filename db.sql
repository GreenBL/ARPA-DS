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
    phone VARCHAR(15) NOT NULL,
    email VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL 
);


CREATE TABLE balance (
    wallet_id INT AUTO_INCREMENT PRIMARY KEY,
    amount DECIMAL(10, 2) NOT NULL,
    ref_user INT UNIQUE, 
    FOREIGN KEY (ref_user) REFERENCES users(id) 
);
