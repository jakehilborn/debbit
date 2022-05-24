LOCATION_OF_DEBBIT = "/home/you/where-this-stuff-goes/debbit"


build:
	docker build -t debbit .

run:
	docker run -v $(LOCATION_OF_DEBBIT)/src/state:/home/debbit/src/state debbit
