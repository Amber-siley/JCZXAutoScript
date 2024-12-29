from copy import deepcopy
from math import floor

class Quarry:
    class Skills:
        class Skill:
            work_minutes = 0
            work_time_str = ""
            mood = 100
            
            def __init__(self, name: str = None, 
                         base_weight: float = 0,
                         elec_weight: float = 0,
                         smelt_weight: float = 0,
                         mood_expend: float = 1,
                         another_expend_weight: float = 0,
                         base_limit_add: int = 0,
                         elec_limit_add: int = 0,
                         smelt_limit_add: int = 0,
                         electric_weight: float = 0,
                         per_hour_base: float = 0,
                         per_hour_elec: float = 0,
                         per_hour_smelt: float = 0
                         ) -> None:
                self.name = name
                self.base_weight = base_weight
                self.elec_weight = elec_weight
                self.smelt_weight = smelt_weight
                self.mood_expend = mood_expend
                self.another_expend_weight = another_expend_weight
                self.base_limit_add = base_limit_add
                self.elec_limit_add = elec_limit_add
                self.smelt_limit_add = smelt_limit_add
                self.electric_weight = electric_weight
                self.per_hour_base = per_hour_base
                self.per_hour_elec = per_hour_elec
                self.per_hour_smelt = per_hour_smelt
        
        麻烦制造者 = Skill("麻烦制造者", 0.2, 0.2, 0.2, base_limit_add = -2000, elec_limit_add = -200, smelt_limit_add = -200)
        监督员α = Skill("监督员α", 0.2, 0.2, 0.2, 1.5)
        监督员β = Skill("监督员β", 0.2, 0.2, 0.2, mood_expend = 1.25, another_expend_weight = 0.25)
        产能优化α = Skill("产能优化α", 0.18)
        产能优化β = Skill("产能优化β", elec_weight = 0.18)
        产能优化γ = Skill("产能优化γ", smelt_weight = 0.18)
        成本存储 = Skill("成本存储", 0.06, 0.06, 0.06, electric_weight = -0.15)
        安抚精英α = Skill("安抚精英α", another_expend_weight = -0.45)
        产能增长α = Skill("产能增长α", 0.05, per_hour_base = 0.03)
        产能增长β = Skill("产能增长β", elec_weight = 0.05, per_hour_elec = 0.03)
        产能增长γ = Skill("产能增长γ", smelt_weight = 0.05, per_hour_smelt = 0.03)
        仓管员α = Skill("仓管员α", base_limit_add = 3000)
        仓管员β = Skill("仓管员β", elec_limit_add = 600)
        仓管员γ = Skill("仓管员γ", smelt_limit_add = 600)
        
        @staticmethod
        def addValue(obj: Skill, add: Skill):
            dirs = [i for i in Quarry.Skills.Skill().__dir__() if not i.startswith("__") and i != "name"]
            for dir in dirs:
                obj.__setattr__(dir, obj.__getattribute__(dir)+add.__getattribute__(dir))

        @staticmethod
        def dirs() -> list[str]:
            return [i for i in Quarry.Skills().__dir__() if isinstance(Quarry.Skills().__getattribute__(i), Quarry.Skills.Skill)]
        
        @staticmethod
        def ls() -> list[Skill]:
            return [Quarry.Skills().__getattribute__(i) for i in Quarry.Skills.dirs()]
        
    def __init__(self) -> None:
        self.level = 10
        self.stations:list[Quarry.Skills.Skill] = []
        self.base_limit = 9000
        self.elec_limit = 1125
        self.smelt_limit = 1125
    
    @property
    def limit(self):
        return (self.base_limit, self.elec_limit, self.smelt_limit)
    
    def price(self, base: int = 0, elec: int = 0, smelt: int = 0) -> int:
        """返回价值"""
        electric_quartz_price = 8
        smelt_quartz_price= 8
        return floor(base)+(floor(elec)*electric_quartz_price)+(floor(smelt)*smelt_quartz_price)

    def setEmplotees(self, *args: Skills.Skill):
        """设置员工"""
        self.workers = deepcopy(list(args))
        self.stations = self.__mergeSameSkill(args)
        self.__initSometing()
    
    def __mergeSameSkill(self, skills: list[Skills.Skill]) -> list[Skills.Skill]:
        tmp_names = []
        tmp_stations: list[Quarry.Skills.Skill] = []
        for i in skills:
            if i.name in tmp_names:
                for j in tmp_stations:
                    if i.name == j.name:
                        self.Skills.addValue(j, i)
                        break
            else:
                tmp_stations.append(deepcopy(i))
                tmp_names.append(i.name)
        return tmp_stations
        
    def __initSometing(self):
        self.__initLimit()
        self.__initworkerTime()
    
    def __initLimit(self):
        self.base_limit = 9000
        self.elec_limit = 1125
        self.smelt_limit = 1125
        for i in self.workers:
            self.base_limit += i.base_limit_add
            self.elec_limit += i.elec_limit_add
            self.smelt_limit += i.smelt_limit_add
    
    @property
    def earnings(self):
        """返回当前产出速度"""
        base = 80
        elec = 10
        smelt = 10
        for i in self.stations:
            base *= (i.base_weight+1)
            elec *= (i.elec_weight+1)
            smelt *= (i.smelt_weight+1)
        base *= 1.2
        elec *= 1.2
        smelt *= 1.2
        return (floor(base),floor(elec),floor(smelt))

    def __initworkerTime(self):
        def mood_speed(mood_speed: int, weights: list[float]):
            for w in weights:
                mood_speed *= (1+w)
            return mood_speed
            
        workers = deepcopy(self.workers)
        self.workers.clear()
        while True:
            if workers:
                for index, i in enumerate(workers):
                    names = [i.name for i in self.workers]
                    if i.name in names:
                        self.workers.append(deepcopy(i))
                        workers.remove(i)
                        continue
                    tmp_workers: list[Quarry.Skills.Skill] = deepcopy(workers)
                    tmp_workers.pop(index)
                    another_mood_expends = [j.another_expend_weight for j in self.__mergeSameSkill(tmp_workers) if j.another_expend_weight]
                    if i.mood <= 0:
                        i.mood = 100
                        i.work_time_str = "{} h {} m".format(int(i.work_minutes//60), int(i.work_minutes%60))
                        self.workers.append(deepcopy(i))
                        workers.remove(i)
                    else:
                        i.work_minutes += 7
                        i.mood -= mood_speed(i.mood_expend, another_mood_expends)
            else:
                self.workers.sort(key = lambda x:x.name, reverse = True)
                break
    
    def workeTime(self) -> list[str]:
        return [i.work_time_str for i in self.workers]
    
    def details(self) -> tuple[list[float]]:
        base, all_base = 80, []
        elec, all_elec = 10, []
        smelt, all_smelt = 10, []
        max_worker = max(self.workers, key = lambda x:x.work_minutes)
        times = int(max_worker.work_minutes//30)
        workers = deepcopy(self.workers)
        stations = self.__mergeSameSkill(workers)
        
        for i in range(1, times+1):
            base = 80
            elec = 10
            smelt = 10
            for j in workers:
                if i*30 > j.work_minutes:
                    workers.remove(j)
                    continue
                
            stations = self.__mergeSameSkill(workers)
                
            for x in stations:
                base *= (x.base_weight+1)
                elec *= (x.elec_weight+1)
                smelt *= (x.smelt_weight+1)

            if i % 2 == 1:
                for z in workers:
                    if z.base_weight >= 0.2: ...
                    else: z.base_weight += z.per_hour_base
                    
                    if z.elec_weight >= 0.2: ...
                    else: z.elec_weight += z.per_hour_elec
                    
                    if z.smelt_weight >= 0.2: ...
                    else: z.smelt_weight += z.per_hour_smelt
            
            all_base.append(base*1.2)
            all_elec.append(elec*1.2)
            all_smelt.append(smelt*1.2)
        return (all_base, all_elec, all_smelt)
    
    def totalHistory(self) -> list[int]:
        base, elec, smelt = map(lambda x: list(map(floor, x)), self.details())
        base = [sum(base[:i]) for i in range(len(base)+1)]
        elec = [sum(elec[:i]) for i in range(len(elec)+1)]
        smelt = [sum(smelt[:i]) for i in range(len(smelt)+1)]
        return (base, elec, smelt) 