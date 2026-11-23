// Linux/Pi event loop: poll stdin without blocking motion ticks.
#include "motion.hpp"
#include <algorithm>
#include <poll.h>
#include <unistd.h>
#include <cerrno>
#include <chrono>
#include <csignal>
#include <iostream>
#include <stdexcept>

int main(int argc,char** argv) {
    std::signal(SIGPIPE,SIG_IGN);
    if(argc!=5||std::string(argv[1])!="--backend"||std::string(argv[2])!="mock"
       ||std::string(argv[3])!="--config") {
        std::cerr<<"Usage: motion_api --backend mock --config config/mock.conf\n"
                   "Hardware mode is not implemented.\n";return 2;
    }
    try {
        Motion m(Config::load(argv[4]),[](const std::string& s){std::cout<<s<<std::endl;});
        typedef std::chrono::steady_clock Clock;
        auto previous=Clock::now();std::string pending;bool discard=false;
        while(std::cout.good()) {
            pollfd input={STDIN_FILENO,POLLIN,0};int result=poll(&input,1,10);
            if(result<0&&errno!=EINTR) throw std::runtime_error("poll_failed");
            if(result>0&&(input.revents&(POLLIN|POLLHUP))) {
                char buffer[1024];ssize_t n=read(STDIN_FILENO,buffer,sizeof buffer);
                if(n==0) {m.shutdown();return 0;}
                if(n<0&&errno!=EINTR) throw std::runtime_error("read_failed");
                for(ssize_t i=0;i<n;++i) {
                    if(buffer[i]=='\n') {
                        if(discard) m.command("0"); else m.command(pending);
                        pending.clear();discard=false;
                    } else if(!discard) {
                        pending+=buffer[i];if(pending.size()>256) {pending.clear();discard=true;}
                    }
                }
            }
            auto now=Clock::now();double dt=std::chrono::duration<double>(now-previous).count();
            previous=now;
            // Integrate bounded virtual steps; elapsed real time includes scheduling delays.
            // Huge host stalls fail the move rather than simulating unlimited catch-up.
            if(dt>1) m.tick(dt);
            else while(dt>0) {double step=std::min(dt,.01);m.tick(step);dt-=step;}
        }
        m.shutdown();return 1;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 2;}
}
