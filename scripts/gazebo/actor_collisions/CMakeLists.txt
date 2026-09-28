cmake_minimum_required(VERSION 3.16)
project(ActorCollisionsPlugin CXX)

# Gazebo 11 example, minimum raised so CMake 4 can configure it.
find_package(gazebo REQUIRED)
include_directories(${GAZEBO_INCLUDE_DIRS})
link_directories(${GAZEBO_LIBRARY_DIRS})
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${GAZEBO_CXX_FLAGS}")

add_library(ActorCollisionsPlugin SHARED ActorCollisionsPlugin.cc)
target_link_libraries(ActorCollisionsPlugin ${GAZEBO_LIBRARIES})
