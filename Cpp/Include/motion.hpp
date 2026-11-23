#ifndef MOTION_HPP
#define MOTION_HPP
#include <functional>
#include <string>
#include <vector>
#include <cstdint>

// Author: [Your name]. COSC303 direct-wheel-control prototype.
// All backend feedback in this version is explicitly simulated.
struct Config {
    double grid_m=.35, circumference_m=.22, track_m=.235;
    double left_cpr=254, right_cpr=254, ticks_per_second=1000;
    double timeout_s=10, stall_s=.5, mismatch_fraction=.25;
    static Config load(const std::string& path);
};
class Motion {
public:
    typedef std::function<void(const std::string&)> Output;
    Motion(const Config& config, Output output);
    void command(const std::string& line);
    void tick(double seconds);
    void shutdown();
private:
    Config c_; Output out_;
    std::string state_="IDLE", fault_;
    std::int64_t last_id_=0, active_id_=0;
    std::int64_t count_[2]={0,0}, start_[2]={0,0}, target_[2]={0,0};
    double fractional_[2]={0,0}, rate_[2]={1,1}, quiet_[2]={0,0};
    bool wd_[2]={false,false}, stalled_[2]={false,false};
    double elapsed_=0, x_=0, y_=0, heading_=0;
    void emit(std::int64_t id,const std::string& status,const std::string& error="");
    void fail(const std::string& fault);
    bool remaining(int i) const;
    void begin(std::int64_t id, double left_m, double right_m);
};
#endif
