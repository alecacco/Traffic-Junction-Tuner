#!/bin/bash

#runs TJTuner automatically managing logging. First parameter is log file name, if set to "auto" will use a timestamp

logprefix="log"
if [ "$1" == 'auto'  ]
    then
        logprefix="`date +%Y-%m-%d_%H-%M-%S`"
    else
        logprefix=$1
fi

#In order to make tee work python works unbuffered. There is an issue with stderr, that's why a separate file is used, printed just because at the end of the execution
python -u TJTuner.py ${@:2:99} 2>$logprefix.err | tee $logprefix.out

cat $logprefix.err
