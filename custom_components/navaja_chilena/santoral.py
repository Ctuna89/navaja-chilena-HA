"""Santoral católico tradicional (santo del día), incluido en la integración.

No usa internet. Es el santoral tradicional de uso común en Chile y Latinoamérica;
otros calendarios pueden asignar un santo distinto a algunos días. Para ajustarlo
basta editar este archivo.
"""

from __future__ import annotations

from datetime import date

# SANTORAL[mes][día - 1]
SANTORAL: dict[int, tuple[str, ...]] = {
    1: (
        "Santa María, Madre de Dios", "San Basilio Magno y San Gregorio Nacianceno",
        "Santa Genoveva", "Santa Ángela de Foligno", "San Simeón Estilita",
        "Epifanía del Señor (Reyes Magos)", "San Raimundo de Peñafort", "San Severino",
        "San Adrián de Canterbury", "San Gonzalo de Amarante", "San Higinio",
        "Santa Tatiana", "San Hilario de Poitiers", "San Félix de Nola",
        "San Pablo el Ermitaño", "San Marcelo I", "San Antonio Abad", "Santa Prisca",
        "San Mario", "San Sebastián", "Santa Inés", "San Vicente", "San Ildefonso",
        "San Francisco de Sales", "Conversión de San Pablo", "San Timoteo y San Tito",
        "Santa Ángela de Mérici", "Santo Tomás de Aquino", "San Valerio",
        "Santa Martina", "San Juan Bosco",
    ),
    2: (
        "Santa Brígida de Kildare", "Presentación del Señor (La Candelaria)", "San Blas",
        "San Andrés Corsini", "Santa Águeda", "San Pablo Miki y compañeros",
        "San Ricardo", "San Jerónimo Emiliani", "Santa Apolonia", "Santa Escolástica",
        "Nuestra Señora de Lourdes", "Santa Eulalia de Barcelona",
        "Santa Catalina de Ricci", "San Valentín", "San Claudio de la Colombière",
        "Santa Juliana", "Siete Santos Fundadores de los Servitas",
        "San Simeón de Jerusalén", "San Conrado", "San Eleuterio", "San Pedro Damián",
        "Cátedra de San Pedro", "San Policarpo", "San Modesto", "San Valero",
        "San Alejandro de Alejandría", "San Gabriel de la Dolorosa", "San Román",
        "San Osvaldo",
    ),
    3: (
        "San Rosendo", "San Simplicio", "Santa Cunegunda", "San Casimiro",
        "San Adrián de Cesarea", "Santa Coleta", "Santas Perpetua y Felicidad",
        "San Juan de Dios", "Santa Francisca Romana", "San Macario de Jerusalén",
        "San Eulogio", "San Luis Orione", "Santa Eufrasia", "Santa Matilde",
        "Santa Luisa de Marillac", "San Heriberto", "San Patricio",
        "San Cirilo de Jerusalén", "San José", "San Cutberto", "San Benjamín",
        "Santa Lea", "Santo Toribio de Mogrovejo", "San Gabriel Arcángel",
        "Anunciación del Señor", "San Ludgero", "San Ruperto", "San Sixto III",
        "San Bertoldo", "San Juan Clímaco", "Santa Balbina",
    ),
    4: (
        "San Hugo de Grenoble", "San Francisco de Paula", "San Sixto I",
        "San Isidoro de Sevilla", "San Vicente Ferrer", "San Celestino I",
        "San Juan Bautista de La Salle", "San Dionisio de Corinto", "Santa Casilda",
        "San Ezequiel Moreno", "San Estanislao", "San Julio I", "San Martín I",
        "San Tiburcio y San Valeriano", "Santa Basilisa", "Santa Bernardita",
        "San Aniceto", "San Perfecto", "San León IX", "Santa Inés de Montepulciano",
        "San Anselmo", "San Sotero", "San Jorge", "San Fidel de Sigmaringa",
        "San Marcos Evangelista", "Nuestra Señora del Buen Consejo", "Santa Zita",
        "San Pedro Chanel", "Santa Catalina de Siena", "San Pío V",
    ),
    5: (
        "San José Obrero", "San Atanasio", "Santos Felipe y Santiago", "San Florián",
        "San Ángel", "San Evodio", "Santa Flavia Domitila", "Nuestra Señora de Luján",
        "San Pacomio", "San Juan de Ávila", "San Francisco de Jerónimo", "San Pancracio",
        "Nuestra Señora de Fátima", "San Matías", "San Isidro Labrador",
        "San Juan Nepomuceno", "San Pascual Bailón", "San Juan I", "San Celestino V",
        "San Bernardino de Siena", "San Cristóbal Magallanes", "Santa Rita de Casia",
        "San Juan Bautista de Rossi", "María Auxiliadora", "San Beda el Venerable",
        "San Felipe Neri", "San Agustín de Canterbury", "San Germán", "San Maximino",
        "San Fernando", "Visitación de la Virgen María",
    ),
    6: (
        "San Justino", "San Marcelino y San Pedro", "San Carlos Lwanga",
        "San Francisco Caracciolo", "San Bonifacio", "San Norberto",
        "San Roberto de Newminster", "San Medardo", "San Efrén",
        "Santa Margarita de Escocia", "San Bernabé", "San Juan de Sahagún",
        "San Antonio de Padua", "San Eliseo", "Santa Micaela",
        "San Juan Francisco Regis", "San Rainiero", "San Gregorio Barbarigo",
        "San Romualdo", "San Silverio", "San Luis Gonzaga", "San Paulino de Nola",
        "San José Cafasso", "Natividad de San Juan Bautista", "San Guillermo",
        "San Josemaría Escrivá", "Nuestra Señora del Perpetuo Socorro", "San Ireneo",
        "San Pedro y San Pablo", "Santos Protomártires de Roma",
    ),
    7: (
        "San Junípero Serra", "San Otón", "Santo Tomás Apóstol", "Santa Isabel de Portugal",
        "San Antonio María Zaccaria", "Santa María Goretti", "San Fermín",
        "San Adrián III", "San Agustín Zhao Rong y compañeros", "Santa Amalia",
        "San Benito de Nursia", "San Juan Gualberto", "San Enrique", "San Camilo de Lelis",
        "San Buenaventura", "Nuestra Señora del Carmen", "San Alejo", "San Federico",
        "Santa Áurea", "San Elías Profeta", "San Lorenzo de Brindis", "Santa María Magdalena",
        "Santa Brígida de Suecia", "Santa Cristina", "Santiago Apóstol",
        "San Joaquín y Santa Ana", "San Pantaleón", "San Nazario", "Santa Marta",
        "San Pedro Crisólogo", "San Ignacio de Loyola",
    ),
    8: (
        "San Alfonso María de Ligorio", "San Eusebio de Vercelli", "Santa Lidia",
        "San Juan María Vianney", "Nuestra Señora de las Nieves",
        "Transfiguración del Señor", "San Cayetano", "Santo Domingo de Guzmán",
        "Santa Teresa Benedicta de la Cruz", "San Lorenzo", "Santa Clara de Asís",
        "Santa Juana Francisca de Chantal", "San Hipólito", "San Maximiliano Kolbe",
        "Asunción de la Virgen María", "San Roque", "San Jacinto", "Santa Elena",
        "San Juan Eudes", "San Bernardo", "San Pío X", "Santa María Reina",
        "Santa Rosa de Lima", "San Bartolomé", "San Luis Rey de Francia",
        "Santa Teresa de Jesús Jornet", "Santa Mónica", "San Agustín de Hipona",
        "Martirio de San Juan Bautista", "San Félix y San Adaucto", "San Ramón Nonato",
    ),
    9: (
        "San Gil", "San Antolín", "San Gregorio Magno", "Santa Rosalía",
        "Santa Teresa de Calcuta", "San Zacarías", "Santa Regina",
        "Natividad de la Virgen María", "San Pedro Claver", "San Nicolás de Tolentino",
        "San Proto", "Santísimo Nombre de María", "San Juan Crisóstomo",
        "Exaltación de la Santa Cruz", "Nuestra Señora de los Dolores",
        "San Cornelio y San Cipriano", "San Roberto Belarmino", "San José de Cupertino",
        "San Jenaro", "San Andrés Kim y compañeros mártires", "San Mateo", "San Mauricio",
        "San Pío de Pietrelcina", "Nuestra Señora de la Merced", "San Cleofás",
        "San Cosme y San Damián", "San Vicente de Paúl", "San Wenceslao",
        "San Miguel, San Gabriel y San Rafael Arcángeles", "San Jerónimo",
    ),
    10: (
        "Santa Teresa del Niño Jesús", "Santos Ángeles Custodios", "San Gerardo",
        "San Francisco de Asís", "Santa Faustina Kowalska", "San Bruno",
        "Nuestra Señora del Rosario", "Santa Pelagia", "San Dionisio",
        "San Francisco de Borja", "San Juan XXIII", "Nuestra Señora del Pilar",
        "San Eduardo", "San Calixto I", "Santa Teresa de Jesús",
        "Santa Margarita María de Alacoque", "San Ignacio de Antioquía",
        "San Lucas Evangelista", "San Pedro de Alcántara", "Santa Irene", "Santa Úrsula",
        "San Juan Pablo II", "San Juan de Capistrano", "San Antonio María Claret",
        "San Crispín", "San Evaristo", "San Florencio", "San Judas Tadeo y San Simón",
        "San Narciso", "San Alonso Rodríguez", "San Quintín",
    ),
    11: (
        "Todos los Santos", "Conmemoración de los Fieles Difuntos", "San Martín de Porres",
        "San Carlos Borromeo", "San Zacarías y Santa Isabel", "San Leonardo",
        "San Ernesto", "San Godofredo", "Dedicación de la Basílica de Letrán",
        "San León Magno", "San Martín de Tours", "San Josafat", "San Diego de Alcalá",
        "San Serapio", "San Alberto Magno", "Santa Gertrudis", "Santa Isabel de Hungría",
        "Dedicación de las Basílicas de San Pedro y San Pablo", "Santa Matilde",
        "San Edmundo", "Presentación de la Virgen María", "Santa Cecilia",
        "San Clemente I", "San Andrés Dung-Lac y compañeros", "Santa Catalina de Alejandría",
        "San Conrado", "San Facundo", "Santiago de la Marca", "San Saturnino",
        "San Andrés Apóstol",
    ),
    12: (
        "San Eloy", "Santa Bibiana", "San Francisco Javier", "Santa Bárbara", "San Sabas",
        "San Nicolás", "San Ambrosio", "Inmaculada Concepción de la Virgen María",
        "San Juan Diego", "Nuestra Señora de Loreto", "San Dámaso I",
        "Nuestra Señora de Guadalupe", "Santa Lucía", "San Juan de la Cruz",
        "San Valeriano", "Santa Adelaida", "San Lázaro", "Nuestra Señora de la Esperanza",
        "San Urbano V", "Santo Domingo de Silos", "San Pedro Canisio",
        "Santa Francisca Javiera Cabrini", "San Juan de Kety", "Santa Irmina",
        "Natividad del Señor (Navidad)", "San Esteban", "San Juan Apóstol y Evangelista",
        "Santos Inocentes", "Santo Tomás Becket", "San Sabino", "San Silvestre I",
    ),
}


def saint_of(day: date) -> str:
    """Santo del día. El 29 de febrero existe también en años no bisiestos del calendario."""
    return SANTORAL[day.month][day.day - 1]
