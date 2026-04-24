SELECT abs(_actual - _target) * ((_met::int * 2) - 1) FROM data;
