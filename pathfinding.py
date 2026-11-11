from collections import deque

#when reading in the 2D matrix, if index = 1, obstacle located at that index
FREE = 0
BLOCKED = 1 

#Indicate which direction Roomba is facing, if facing "up", DIRS[1]. 
#When performing a CW or CC turn, DIRS[current +/- 1]
DIRS = [(1,0), (0,1), (-1,0), (0,-1)] 

#Generate neighbors as needed
def neighbors(matrix, width, height, x, y): 
    for dx, dy in DIRS: 
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height and matrix[ny][nx] == FREE:
            yield nx, ny #One item stored in memory at a time, not a "final result" (googled)

#BFS, returns list of (x,y) nodes from start to goal or none
def shortest_path(matrix, start, goal): 
    height = len(matrix)
    width = len(matrix[0])
    n = width * height 

    #1D indexing
    src = start[1] * width + start[0]
    dst = goal[1] * width + goal[0]

    visited = [False] * n #T when node in Q 
    parent = [-1] * n  #The node we came from on shorest route
    queue = deque()  

    visited[src] = True
    queue.append(src)

    found = (src == dst) 
    while queue and not found: 
        u = queue.popleft() 
        ux, uy = u % width, u // width

        #generate neighbors on the fly
        for vx, vy in neighbors(matrix, width, height, ux, uy): 
            v = vy * width + vx
            #skip, already visited 
            if visited[v]:
                continue
            visited[v] = True #mark visited when queued 
            parent[v] = u
            if v == dst: #First encounter with goal is shortest route with BFS
                found = True
                break
            queue.append(v) 

    if not found: 
        return "No Path Found" #No path to goal 
    
    #Traverse parent[] from goal -> start, reverse 
    path = []
    v = dst
    while v != -1: 
        path.append((v % width, v // width))
        v = parent[v]
    path.reverse()
    return path 

#Heading default = 0 -> starts facing east at (0,0)
def path_to_commands(path, heading=0): 
    commands = []
    run = 0 #How many nodes in a row to travel w/o rotating
    for i in range(len(path) - 1): 
        step = (path[i+1][0] - path[i][0], path[i+1][1] - path[i][1]) 
        d = DIRS.index(step) #determines direction that needs to be faced
        if d != heading: #Check if already facing that direction
            if run: 
                commands.append(str(run)) 
            turn = (d - heading) % 4 #1 = CC, 2 = CC CC, 3 = CW. 0 Not possible as d != heading checked
            commands.extend({1 : ["CC"], 2: ["CC", "CC"], 3: ["CW"]}[turn]) #Google for how to implement this logic in python
            heading = d #Update current direction
            run = 0 #Reset run
        run += 1
    if run: #If run != 0, must traverse before turning again
        commands.append(str(run)) #standardize all outputs as strings
    #returns list of commands and direction being faced at end (heading)
    #Unsure how we will handle returning to dock as of rn? Code needed or can it just do that?
    return commands, heading 
