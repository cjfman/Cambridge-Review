## https://davidmathlogic.com/colorblind/#%23332288-%23117733-%2344AA99-%2388CCEE-%23DDCC77-%23CC6677-%23AA4499-%23882255
COLOR_BLIND_FRIENDLY_HEX = [
    "#332288", ## Dark Blue
    "#117733", ## Green
    "#44AA99", ## Turquoise
    "#88CCEE", ## Light Blue
    "#DDCC77", ## Yellow
    "#CC6677", ## Salmon
    "#AA4499", ## Purple
    "#882255", ## Dark Pink
]
COLOR_BLIND_FRIENDLY = [
    (51, 34, 136),   ## Dark Blue
    (17, 119, 51),   ## Green
    (68, 170, 153),  ## Turquoise
    (136, 204, 238), ## Light Blue
    (221, 204, 119), ## Yellow
    (204, 102, 119), ## Salmon
    (170, 68, 153),  ## Purple
    (136, 34, 85),   ## Dark Pink
]
COLOR_BLIND_FRIENDLY.reverse()
GREY = (68, 68, 68)

class ColorGradient:
    def __init__(self, colors, max_val, min_val=0, *, scale_fn=None):
        self.colors       = colors
        self.max          = max_val
        self.min          = min_val
        self.range        = self.max - self.min
        self.size         = len(self.colors)
        self.factor       = 1
        self.scale_fn     = scale_fn or (lambda x: x)
        self.min_scaled   = self.scale_fn(self.min) if self.min > 0 else self.min
        self.max_scaled   = self.scale_fn(self.max*self.factor)
        self.range_scaled = self.max_scaled - self.min_scaled

    def scale(self, val):
        try:
            return self.scale_fn((val-self.min)*self.factor)
        except:
            return 0

    def percent(self, val):
        if val is None or val < self.min:
            return 0
        elif val > self.max:
            return 100

        return self.scale(val)*100/self.range_scaled

    def pick(self, val):
        if val is None:
            return '#000000'
        elif val < self.min:
            return self.colors[0]
        elif val > self.max:
            return self.colors[-1]

        index = int(max(min(self.scale(val)*self.size//self.range_scaled, self.size - 1), 0))
        return self.colors[index]

    def __str__(self):
        return f"Size:{self.size} Max:{self.max} Min:{self.min} Range:{self.range}" \
            + f" MaxScaled:{self.max_scaled} MinScaled:{self.min_scaled} RangeScaled:{self.range_scaled}"


## https://gka.github.io/palettes/#/256|d|648fff,785ef0,dc267f|dc267f,fe6100,ffb000|0|1
## #648fff, #785ef0, #dc267f -- #dc267f, #fe6100, #ffb000
BlueRedYellow = [
    '#648fff', '#648eff', '#658eff', '#668dfe', '#668cfe', '#678bfe', '#678bfd', '#688afd',
    '#6889fd', '#6989fc', '#6a88fc', '#6a87fc', '#6b86fb', '#6c86fb', '#6d85fa', '#6d84fa',
    '#6e84fa', '#6f83f9', '#7082f9', '#7181f8', '#7181f8', '#7280f7', '#737ff7', '#747ff6',
    '#757ef6', '#767df5', '#777df5', '#777cf4', '#787bf3', '#797bf3', '#7a7af2', '#7b79f2',
    '#7c78f1', '#7d78f0', '#7e77f0', '#7f76ef', '#8076ee', '#8175ee', '#8274ed', '#8374ec',
    '#8473ec', '#8572eb', '#8671ea', '#8771e9', '#8870e8', '#896fe8', '#8a6fe7', '#8b6ee6',
    '#8c6de5', '#8d6de4', '#8e6ce4', '#8f6be3', '#906ae2', '#916ae1', '#9269e0', '#9368df',
    '#9468de', '#9667dd', '#9766dc', '#9865db', '#9965da', '#9a64d9', '#9b63d8', '#9c63d7',
    '#9d62d6', '#9e61d5', '#9f60d4', '#a060d3', '#a15fd2', '#a25ed1', '#a35dd0', '#a45dcf',
    '#a55cce', '#a65bcd', '#a75acc', '#a85acb', '#a959c9', '#ab58c8', '#ac57c7', '#ad57c6',
    '#ae56c5', '#af55c3', '#b054c2', '#b153c1', '#b253c0', '#b352bf', '#b451bd', '#b550bc',
    '#b64fbb', '#b74fb9', '#b84eb8', '#b94db7', '#ba4cb5', '#bb4bb4', '#bc4ab3', '#bd4ab1',
    '#be49b0', '#bf48af', '#c047ad', '#c146ac', '#c245aa', '#c344a9', '#c443a8', '#c543a6',
    '#c642a5', '#c741a3', '#c840a2', '#c93fa0', '#ca3e9f', '#cb3d9d', '#cb3c9c', '#cc3b9a',
    '#cd3a99', '#ce3997', '#cf3896', '#d03694', '#d13593', '#d23491', '#d3338f', '#d4328e',
    '#d5318c', '#d6308b', '#d72e89', '#d82d87', '#d82c86', '#d92a84', '#da2982', '#db2781',
    '#dd277e', '#dd287c', '#de2a7b', '#df2b79', '#df2c78', '#e02d77', '#e12e75', '#e13074',
    '#e23172', '#e23271', '#e33370', '#e4346f', '#e4356d', '#e5366c', '#e5386b', '#e63969',
    '#e63a68', '#e73b67', '#e73c66', '#e83d64', '#e83e63', '#e93f62', '#e94061', '#ea4260',
    '#ea435e', '#eb445d', '#eb455c', '#ec465b', '#ec475a', '#ed4859', '#ed4958', '#ee4a57',
    '#ee4b55', '#ee4c54', '#ef4d53', '#ef4e52', '#f04f51', '#f05050', '#f0524f', '#f1534e',
    '#f1544d', '#f1554c', '#f2564b', '#f2574a', '#f35849', '#f35948', '#f35a47', '#f45b46',
    '#f45c45', '#f45d44', '#f45e43', '#f55f42', '#f56041', '#f56140', '#f6623f', '#f6633e',
    '#f6643d', '#f7653c', '#f7663b', '#f7683a', '#f76939', '#f86a38', '#f86b37', '#f86c36',
    '#f86d35', '#f96e35', '#f96f34', '#f97033', '#f97132', '#fa7231', '#fa7330', '#fa742f',
    '#fa752e', '#fb762d', '#fb772c', '#fb782b', '#fb792a', '#fb7a29', '#fc7b29', '#fc7c28',
    '#fc7d27', '#fc7f26', '#fc8025', '#fc8124', '#fd8223', '#fd8322', '#fd8421', '#fd8520',
    '#fd861f', '#fd871e', '#fd881d', '#fe891c', '#fe8a1b', '#fe8b1a', '#fe8c19', '#fe8d18',
    '#fe8e17', '#fe8f16', '#fe9015', '#fe9214', '#ff9313', '#ff9412', '#ff9511', '#ff9610',
    '#ff970f', '#ff980e', '#ff990d', '#ff9a0c', '#ff9b0b', '#ff9c0a', '#ff9d09', '#ff9e08',
    '#ffa007', '#ffa106', '#ffa205', '#ffa304', '#ffa403', '#ffa503', '#ffa602', '#ffa702',
    '#ffa801', '#ffa901', '#ffaa00', '#ffac00', '#ffad00', '#ffae00', '#ffaf00', '#ffb000',
]


#https://gka.github.io/palettes/#/256|d|648fff|ffb000|0|1
BlueYellow = [
    '#002d89', '#012e8b', '#03308d', '#04328f', '#063391', '#073593', '#093695', '#0a3897',
    '#0b3a99', '#0d3b9b', '#0e3d9d', '#103f9f', '#1140a1', '#1342a3', '#1444a5', '#1545a7',
    '#1747a9', '#1848ab', '#1a4aad', '#1b4caf', '#1c4db1', '#1e4fb3', '#1f51b5', '#2152b7',
    '#2254b9', '#2456bb', '#2557bd', '#2659bf', '#285ac1', '#295cc3', '#2b5ec5', '#2c5fc7',
    '#2e61c9', '#2f63cb', '#3064cd', '#3266cf', '#3368d1', '#3569d3', '#366bd5', '#386cd7',
    '#396ed9', '#3a70db', '#3c71dd', '#3e73df', '#4075df', '#4277e0', '#4579e1', '#477be2',
    '#497de2', '#4c7ee3', '#4e80e4', '#5082e5', '#5384e5', '#5586e6', '#5788e7', '#5a8ae8',
    '#5c8ce8', '#5e8ee9', '#618fea', '#6391eb', '#6593ec', '#6895ec', '#6a97ed', '#6c99ee',
    '#6f9bef', '#719def', '#739ff0', '#76a0f1', '#78a2f2', '#7aa4f2', '#7da6f3', '#7fa8f4',
    '#81aaf5', '#84acf6', '#86aef6', '#88b0f7', '#8bb1f8', '#8db3f9', '#8fb5f9', '#92b7fa',
    '#94b9fb', '#96bbfc', '#99bdfc', '#9bbffd', '#9dc1fe', '#a0c2ff', '#a2c4ff', '#a4c5ff',
    '#a6c6fe', '#a8c7fe', '#aac9fe', '#accafe', '#aecbfd', '#b0ccfd', '#b2cdfd', '#b4cefd',
    '#b6d0fd', '#b8d1fc', '#bad2fc', '#bcd3fc', '#bed4fc', '#c0d5fb', '#c2d7fb', '#c4d8fb',
    '#c6d9fb', '#c7dafa', '#c9dbfa', '#cbdcfa', '#cddefa', '#cfdff9', '#d1e0f9', '#d3e1f9',
    '#d5e2f9', '#d7e3f9', '#d9e5f8', '#dbe6f8', '#dde7f8', '#dfe8f8', '#e1e9f7', '#e3eaf7',
    '#e5ecf7', '#e7edf7', '#e9eef6', '#ebeff6', '#edf0f6', '#eff1f6', '#f1f3f5', '#f3f4f5',
    '#f5f4f0', '#f5f2eb', '#f6f1e5', '#f6efe0', '#f6eedb', '#f6edd6', '#f7ebd1', '#f7eacb',
    '#f7e8c6', '#f7e7c1', '#f8e6bc', '#f8e4b7', '#f8e3b2', '#f8e1ac', '#f9e0a7', '#f9dfa2',
    '#f9dd9d', '#f9dc98', '#f9da92', '#fad98d', '#fad888', '#fad683', '#fad57e', '#fbd378',
    '#fbd273', '#fbd16e', '#fbcf69', '#fcce64', '#fccc5e', '#fccb59', '#fcc954', '#fdc84f',
    '#fdc74a', '#fdc545', '#fdc43f', '#fdc23a', '#fec135', '#fec030', '#febe2b', '#febd25',
    '#ffbb20', '#ffba1b', '#feb817', '#fcb717', '#fab516', '#f8b316', '#f6b115', '#f4af15',
    '#f2ad14', '#f0ab13', '#eea913', '#eca812', '#eaa612', '#e8a411', '#e6a211', '#e4a010',
    '#e29e10', '#e09c0f', '#de9a0f', '#dc990e', '#da970d', '#d8950d', '#d6930c', '#d4910c',
    '#d28f0b', '#d08d0b', '#ce8b0a', '#cc8a0a', '#ca8809', '#c88608', '#c68408', '#c48207',
    '#c28007', '#c07e06', '#be7c06', '#bc7b05', '#ba7905', '#b87704', '#b67503', '#b47303',
    '#b27102', '#b06f02', '#ae6d01', '#ac6c01', '#aa6a00', '#a86800', '#a66600', '#a46400',
    '#a26300', '#a06100', '#9e5f00', '#9c5e00', '#9a5c00', '#985a00', '#975900', '#955700',
    '#935500', '#915300', '#8f5200', '#8d5000', '#8b4e00', '#894d00', '#874b00', '#854900',
    '#834800', '#814600', '#7f4400', '#7d4200', '#7b4100', '#793f00', '#783d00', '#763c00',
    '#743a00', '#723800', '#703700', '#6e3500', '#6c3300', '#6a3100', '#683000', '#662e00',
    '#642c00', '#622b00', '#602900', '#5e2700', '#5c2600', '#5a2400', '#592200', '#572000',
]
