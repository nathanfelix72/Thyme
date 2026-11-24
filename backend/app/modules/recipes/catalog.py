"""Small, curated recipe set used by the Phase 1 search MVP.

Phase 2 can replace this catalog with recipes saved by the recipe import flow.
"""

from app.modules.recipes.service import RecipeRecord


SEED_RECIPES: tuple[RecipeRecord, ...] = (
    RecipeRecord(
        id="lemon-chickpea-couscous",
        title="Lemon Chickpea Couscous Bowls",
        body="A bright, filling vegetarian bowl with chickpeas, couscous, spinach, cucumber, feta, and lemon.",
        prep_minutes=20,
        ingredients=("1 cup couscous", "1 can chickpeas, rinsed", "2 cups spinach", "1 cucumber", "1 lemon", "1/3 cup feta", "2 tablespoons olive oil"),
        instructions=("Prepare couscous according to package directions.", "Warm chickpeas in olive oil with salt and pepper.", "Stir lemon zest and juice into the couscous, then serve with spinach, cucumber, chickpeas, and feta."),
        tags=("vegetarian", "quick", "high fiber", "lunch", "weeknight"),
    ),
    RecipeRecord(
        id="potato-black-bean-skillet",
        title="Potato and Black Bean Skillet",
        body="A hearty one-pan vegetarian dinner that uses potatoes, black beans, corn, and smoky spices.",
        prep_minutes=30,
        ingredients=("3 medium potatoes, diced", "1 can black beans, rinsed", "1 cup corn", "1 red bell pepper", "1 teaspoon smoked paprika", "1/2 teaspoon cumin", "1 tablespoon olive oil", "lime and cilantro to serve"),
        instructions=("Dice potatoes into small cubes. Cook in oil in a covered skillet for 12–15 minutes, stirring occasionally.", "Add bell pepper, paprika, and cumin; cook until tender.", "Fold in black beans and corn and heat through. Finish with lime and cilantro."),
        tags=("vegetarian", "one pan", "potatoes", "beans", "budget friendly", "weeknight"),
    ),
    RecipeRecord(
        id="sheet-pan-chicken-potatoes",
        title="Sheet-Pan Chicken, Potatoes, and Broccoli",
        body="An easy balanced dinner of roasted chicken, potatoes, and broccoli with lemon and garlic.",
        prep_minutes=40,
        ingredients=("1 pound chicken breast", "1 pound baby potatoes, halved", "1 head broccoli, cut into florets", "2 tablespoons olive oil", "2 cloves garlic", "1 lemon", "1 teaspoon dried oregano"),
        instructions=("Heat oven to 425°F. Toss potatoes with half the oil, garlic, oregano, salt, and pepper.", "Roast potatoes for 15 minutes. Add chicken and broccoli tossed with the remaining oil.", "Roast for 18–22 minutes, until chicken is cooked through and vegetables are tender. Squeeze lemon over everything."),
        tags=("dinner", "sheet pan", "chicken", "potatoes", "family friendly"),
    ),
    RecipeRecord(
        id="spinach-white-bean-pasta",
        title="Creamy Spinach and White Bean Pasta",
        body="A quick meatless pasta with white beans, spinach, parmesan, and a creamy lemon sauce.",
        prep_minutes=25,
        ingredients=("8 ounces pasta", "1 can white beans, rinsed", "3 cups spinach", "1/3 cup grated parmesan", "1/2 cup reserved pasta water", "1 lemon", "1 tablespoon olive oil"),
        instructions=("Cook pasta until al dente and reserve half a cup of pasta water.", "Warm beans and olive oil in a skillet. Add spinach until wilted.", "Toss in pasta, parmesan, lemon juice, and enough pasta water to make a light sauce."),
        tags=("vegetarian", "quick", "pasta", "beans", "weeknight"),
    ),
    RecipeRecord(
        id="peanut-tofu-noodles",
        title="Peanut Tofu Noodles",
        body="A fast, savory vegetarian noodle bowl with crispy tofu, vegetables, and a peanut-lime sauce.",
        prep_minutes=25,
        ingredients=("8 ounces noodles", "14 ounces firm tofu", "1 bell pepper, sliced", "2 cups shredded cabbage", "3 tablespoons peanut butter", "1 lime", "1 tablespoon soy sauce", "1 teaspoon maple syrup"),
        instructions=("Cook noodles according to package directions.", "Press and cube tofu, then pan-fry until golden. Add bell pepper and cabbage and cook until just tender.", "Whisk peanut butter, lime juice, soy sauce, maple syrup, and warm water. Toss with noodles and tofu."),
        tags=("vegetarian", "vegan option", "quick", "noodles", "high protein"),
    ),
    RecipeRecord(
        id="tomato-egg-skillet",
        title="Tomato and Egg Skillet",
        body="A simple one-pan meal of eggs simmered in seasoned tomatoes, served with toast.",
        prep_minutes=20,
        ingredients=("1 can crushed tomatoes", "4 eggs", "1 small onion, diced", "1 clove garlic", "1/2 teaspoon cumin", "1/2 teaspoon paprika", "bread to serve"),
        instructions=("Soften onion in a skillet, then add garlic, cumin, and paprika.", "Add tomatoes and simmer for 8 minutes.", "Make small wells, add eggs, cover, and cook until the whites are set. Serve with bread."),
        tags=("vegetarian", "quick", "one pan", "breakfast", "budget friendly"),
    ),
    RecipeRecord(
        id="sweet-potato-tacos",
        title="Roasted Sweet Potato and Black Bean Tacos",
        body="Colorful vegetarian tacos with roasted sweet potatoes, black beans, cabbage, and lime yogurt.",
        prep_minutes=35,
        ingredients=("2 sweet potatoes, cubed", "1 can black beans, rinsed", "8 small tortillas", "2 cups shredded cabbage", "1 teaspoon chili powder", "1/2 cup plain yogurt", "1 lime"),
        instructions=("Heat oven to 425°F. Toss sweet potatoes with oil, chili powder, salt, and pepper and roast for 25 minutes.", "Warm black beans and tortillas.", "Mix yogurt with lime juice. Fill tortillas with sweet potatoes, beans, cabbage, and lime yogurt."),
        tags=("vegetarian", "tacos", "sweet potato", "beans", "family friendly"),
    ),
    RecipeRecord(
        id="lentil-vegetable-soup",
        title="Lentil Vegetable Soup",
        body="A comforting, filling soup with lentils, carrots, celery, tomatoes, and vegetable broth.",
        prep_minutes=45,
        ingredients=("1 cup brown lentils, rinsed", "2 carrots, diced", "2 celery stalks, diced", "1 onion, diced", "1 can diced tomatoes", "6 cups vegetable broth", "1 teaspoon dried thyme"),
        instructions=("Soften onion, carrots, and celery in a large pot.", "Add lentils, tomatoes, broth, thyme, salt, and pepper.", "Simmer 30–35 minutes, until lentils are tender. Add water if the soup becomes too thick."),
        tags=("vegetarian", "vegan", "soup", "high fiber", "make ahead", "budget friendly"),
    ),
)
