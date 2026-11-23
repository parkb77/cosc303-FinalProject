#include "motion.hpp"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <locale>
#include <map>
#include <sstream>
#include <stdexcept>

namespace {
const double PI=3.14159265358979323846;
bool integer(const std::string& s,std::int64_t& n) {
    if(s.empty()) return false;
    std::istringstream in(s); in.imbue(std::locale::classic());
    char extra; return bool(in>>n) && !(in>>extra);
}
double wrap(double a) { return std::atan2(std::sin(a),std::cos(a)); }
}
Config Config::load(const std::string& path) {
    Config c; std::ifstream f(path.c_str());
    if(!f) throw std::runtime_error("cannot_open_config");
    std::map<std::string,double*> fields={{"grid_m",&c.grid_m},
      {"circumference_m",&c.circumference_m},{"track_m",&c.track_m},
      {"left_cpr",&c.left_cpr},{"right_cpr",&c.right_cpr},
      {"ticks_per_second",&c.ticks_per_second},{"timeout_s",&c.timeout_s},
      {"stall_s",&c.stall_s},{"mismatch_fraction",&c.mismatch_fraction}};
    std::map<std::string,bool> seen;
    std::string line;
    while(std::getline(f,line)) {
        line=line.substr(0,line.find('#'));
        if(line.find_first_not_of(" \t\r")==std::string::npos) continue;
        std::replace(line.begin(),line.end(),'=',' ');
        std::istringstream in(line);std::string key,extra;double value;
        if(!(in>>key>>value) || in>>extra || !fields.count(key) || seen[key]
           || !std::isfinite(value) || value<=0 || value>1e6)
            throw std::runtime_error("invalid_config");
        *fields[key]=value; seen[key]=true;
    }
    if(c.mismatch_fraction>=1) throw std::runtime_error("invalid_mismatch_fraction");
    return c;
}
Motion::Motion(const Config& c,Output output):c_(c),out_(output) {}
void Motion::emit(std::int64_t id,const std::string& status,const std::string& error) {
    // All strings serialized here are fixed internal tokens, not raw user input.
    std::ostringstream s;s.imbue(std::locale::classic());s<<std::setprecision(12);
    s<<"{\"id\":"<<id<<",\"status\":\""<<status<<"\",\"backend\":\"mock\","
     <<"\"state\":\""<<state_<<"\",\"active_id\":"<<active_id_
     <<",\"fault\":\""<<fault_<<"\",\"error\":\""<<error<<"\","
     <<"\"left_count\":"<<count_[0]<<",\"right_count\":"<<count_[1]
     <<",\"left_target\":"<<target_[0]<<",\"right_target\":"<<target_[1]
     <<",\"left_wd\":"<<(wd_[0]?"true":"false")
     <<",\"right_wd\":"<<(wd_[1]?"true":"false")
     <<",\"pose_source\":\"mock_odometry\",\"pose\":{\"x_m\":"<<x_
     <<",\"y_m\":"<<y_<<",\"heading_rad\":"<<heading_<<"}}";
    out_(s.str());
}
bool Motion::remaining(int i) const {
    return std::llabs(count_[i]-start_[i])<std::llabs(target_[i]);
}
void Motion::fail(const std::string& fault) {
    std::int64_t id=active_id_;active_id_=0;state_="FAULT";fault_=fault;
    fractional_[0]=fractional_[1]=0;
    if(id) emit(id,"failed",fault);
}
void Motion::begin(std::int64_t id,double left,double right) {
    if(state_=="FAULT") { emit(id,"rejected","fault_latched");return; }
    if(active_id_) { emit(id,"rejected","busy");return; }
    if(wd_[0]||wd_[1]) { fail("wheel_drop");emit(id,"rejected","wheel_drop");return; }
    double a=left*c_.left_cpr/c_.circumference_m;
    double b=right*c_.right_cpr/c_.circumference_m;
    if(!std::isfinite(a)||!std::isfinite(b)||std::abs(a)>1e12||std::abs(b)>1e12)
        {emit(id,"rejected","target_out_of_range");return;}
    target_[0]=std::llround(a);target_[1]=std::llround(b);
    for(int i=0;i<2;++i) {start_[i]=count_[i];quiet_[i]=0;fractional_[i]=0;}
    elapsed_=0;active_id_=id;state_="MOVING";emit(id,"accepted");
    if(!remaining(0)&&!remaining(1)) {active_id_=0;state_="IDLE";emit(id,"completed");}
}
void Motion::command(const std::string& line) {
    std::istringstream in(line);std::vector<std::string> a;std::string word;
    while(in>>word) a.push_back(word);
    std::int64_t id;
    if(a.empty()||!integer(a[0],id)||id<=0) {emit(0,"rejected","invalid_id");return;}
    if(id<=last_id_) {emit(id,"rejected","id_not_increasing");return;} last_id_=id;
    if(a.size()<2) {emit(id,"rejected","missing_command");return;}
    const std::string& cmd=a[1]; std::int64_t n;
    if(cmd=="MOVE") {
        if(a.size()!=3||!integer(a[2],n)||n<-20||n>20) {emit(id,"rejected","invalid_move");return;}
        begin(id,n*c_.grid_m,n*c_.grid_m);
    } else if(cmd=="TURN") {
        if(a.size()!=4||(a[2]!="CW"&&a[2]!="CCW")||!integer(a[3],n)||n<1||n>4)
            {emit(id,"rejected","invalid_turn");return;}
        double d=c_.track_m*PI*n/4.0;
        begin(id,a[2]=="CW"?d:-d,a[2]=="CW"?-d:d);
    } else if(cmd=="STOP"&&a.size()==2) {
        std::int64_t old=active_id_;active_id_=0;
        if(state_!="FAULT") state_="IDLE";
        fractional_[0]=fractional_[1]=0;
        if(old) emit(old,"cancelled","stopped");
        emit(id,"completed"); // STOP never clears a latched fault.
    } else if(cmd=="GET_STATE"&&a.size()==2) { emit(id,"completed");
    } else if(cmd=="CLEAR_FAULT"&&a.size()==2) {
        if(active_id_) emit(id,"rejected","busy");
        else if(wd_[0]||wd_[1]) emit(id,"rejected","wheel_drop_active");
        else {state_="IDLE";fault_.clear();emit(id,"completed");}
    } else if(cmd=="MOCK"&&a.size()==5&&(a[3]=="L"||a[3]=="R")) {
        int i=a[3]=="L"?0:1;
        if(a[2]=="WD" && (a[4]=="0"||a[4]=="1")) {
            wd_[i]=a[4]=="1";if(wd_[i]) fail("wheel_drop");emit(id,"completed");
        } else if(a[2]=="STALL"&&(a[4]=="0"||a[4]=="1")) {
            stalled_[i]=a[4]=="1";emit(id,"completed");
        } else if(a[2]=="RATE"&&integer(a[4],n)&&n>=1&&n<=200) {
            rate_[i]=n/100.0;emit(id,"completed");
        } else emit(id,"rejected","invalid_mock");
    } else emit(id,"rejected","invalid_command");
}
void Motion::tick(double dt) {
    if(!active_id_||dt<=0) return;
    if(wd_[0]||wd_[1]) {fail("wheel_drop");return;}
    elapsed_+=dt;
    if(elapsed_>=c_.timeout_s) {fail("movement_timeout");return;}
    double travel[2]={0,0};bool no_progress=false;
    for(int i=0;i<2;++i) {
        if(!remaining(i)) continue;
        if(!stalled_[i]) fractional_[i]+=c_.ticks_per_second*rate_[i]*dt;
        std::int64_t steps=static_cast<std::int64_t>(fractional_[i]);
        fractional_[i]-=steps;
        steps=std::min<long long>(steps,std::llabs(target_[i])-std::llabs(count_[i]-start_[i]));
        int sign=target_[i]<0?-1:1;
        count_[i]+=sign*steps;
        travel[i]=sign*steps*c_.circumference_m/(i==0?c_.left_cpr:c_.right_cpr);
        quiet_[i]=steps?0:quiet_[i]+dt;
        if(remaining(i)&&quiet_[i]>=c_.stall_s) no_progress=true;
    }
    double ds=(travel[0]+travel[1])/2.0;
    double da=(travel[1]-travel[0])/c_.track_m;
    double scale=std::abs(da)<1e-12?1.0:std::sin(da/2)/(da/2);
    x_+=ds*scale*std::cos(heading_+da/2);y_+=ds*scale*std::sin(heading_+da/2);
    heading_=wrap(heading_+da);
    if(no_progress) {fail("encoder_no_progress");return;}
    double progress[2];
    for(int i=0;i<2;++i) progress[i]=target_[i]==0?1.0:
        double(std::llabs(count_[i]-start_[i]))/std::llabs(target_[i]);
    if(elapsed_>.3&&std::abs(progress[0]-progress[1])>c_.mismatch_fraction)
        {fail("wheel_mismatch");return;}
    if(!remaining(0)&&!remaining(1)) {
        std::int64_t old=active_id_;active_id_=0;state_="IDLE";emit(old,"completed");
    }
}
void Motion::shutdown() {
    std::int64_t old=active_id_;active_id_=0;state_="IDLE";
    if(old) emit(old,"cancelled","input_closed");
}
