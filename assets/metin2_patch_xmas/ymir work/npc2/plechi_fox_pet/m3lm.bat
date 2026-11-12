:main
@echo OFF
@color 1a
@title By M3lm
@echo $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$                
@echo           The Best Extension Changer            
@echo               Copyright 2013-2014    
@echo                     By M3lm
@echo $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$


:rename
set OLD=
set /P OLD=Choose old extension   : %=%
if "%OLD%" == "" GOTO error
set NEW=
set /P NEW=Write new extension : %=%
if "%NEW%" == "" GOTO error
@ren *.%OLD% *.%NEW%
@echo The file .%OLD% has been renamed to .%NEW%
@echo ---
GOTO fine
:errore
@echo Error!
@echo Choose a valid extension!
@echo Close and reopen the program.
@echo ---
GOTO Exit
:fine
@echo All Done !
:Iesire
@pause