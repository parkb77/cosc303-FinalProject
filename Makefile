CXX = g++
CXXFLAGS = -std=c++11 -Wall -Wextra -Wpedantic -O2
CPPFLAGS = -Icpp/include
TARGET = build/vacuum_api
SOURCES = cpp/src/main.cpp cpp/src/mock_robot.cpp

.PHONY: all test demo clean
all: $(TARGET)

$(TARGET): $(SOURCES) cpp/include/robot_api.hpp
	mkdir -p build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(SOURCES) -o $(TARGET)

test: $(TARGET)
	python3 -m unittest discover -s tests -v

demo: $(TARGET)
	python3 python/connector.py

clean:
	rm -f $(TARGET)
