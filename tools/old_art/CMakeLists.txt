# grlist (tools/old_art.py): lists the textures of Granny models and writes
# OLD's custom ones (tag 0x71000039) as standard files. It links the Granny
# that nova-client-src ships, so the files it writes are ones NEW's loader reads:
#   cmake -S tools/old_art -B <build> -A x64 -DNOVA_CLIENT_SRC=<nova-client-src checkout>
#   cmake --build <build> --config Release
cmake_minimum_required(VERSION 3.20)
project(grlist CXX)
set(NOVA_CLIENT_SRC "" CACHE PATH "A nova-client-src checkout (its extern/ has Granny)")
if(NOT EXISTS "${NOVA_CLIENT_SRC}/extern/include/granny.h")
	message(FATAL_ERROR "set NOVA_CLIENT_SRC to a nova-client-src checkout")
endif()
add_executable(grlist grlist.cpp)
target_include_directories(grlist PRIVATE "${NOVA_CLIENT_SRC}/extern/include")
target_compile_definitions(grlist PRIVATE BUILDING_GRANNY_STATIC GRANNY_THREADED)
target_link_libraries(grlist PRIVATE "${NOVA_CLIENT_SRC}/extern/library/Granny/granny2_static.lib")
set_property(TARGET grlist PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded")
