.PHONY: install stop run docker-run

install:
	./make.sh install

stop:
	./make.sh stop

run:
	./make.sh run

docker-run:
	./make.sh docker-run
